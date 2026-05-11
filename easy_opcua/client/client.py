""" OPCUAClient: async OPC UA client running in a dedicated thread.
Mirrors OPCUAServer structure: Thread → asyncio loop → async worker with reconnect logic.
"""
import asyncio as aio
from time import sleep
from threading import Thread
from pathlib import Path
from asyncua import Client, ua
from asyncua.ua import SecurityPolicyType
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from cryptography.x509.oid import ExtendedKeyUsageOID
from .data_types import OpcUaClientStatus, OpcUaClientStatusClass, NameSpaceMissingError, DisconnectError
from .client_config import OpcUaClientConfig
from .tag_manager import ClientTagManager
import logging

log = logging.getLogger(__name__)

class OPCUAClient(Thread):
    """OPCUAClient: asynchronous OPC UA client running in a separate thread.
    Manages node fetching, tag subscriptions, and automatic reconnection
    via a ClientTagManager.
    """

    def __init__(self, config: OpcUaClientConfig, tag_manager: ClientTagManager = None, certs_dir: str = None):
        super().__init__(name=config.client_name, daemon=True)
        self._certs_dir = Path.cwd() / "certs" if not certs_dir else Path(certs_dir)
        self._certs_dir.mkdir(exist_ok=True)
        self.config = config
        self._tag_manager = tag_manager or ClientTagManager()
        self._opcua_status = OpcUaClientStatusClass(config.client_name)
        self._aio_stop_event = aio.Event()
        self._client: Client = None
        self._loop: aio.AbstractEventLoop = None
        self.namespace_idx: int = None

    # ------------------------------------------------------------------
    # Thread lifecycle  (mirrors OPCUAServer)
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Entry point for the dedicated client thread."""
        self._loop = aio.new_event_loop()
        aio.set_event_loop(self._loop)
        try:
            while not self._aio_stop_event.is_set():
                try:
                    self._loop.run_until_complete(self._async_worker())
                except Exception as e:
                    log.exception(f"OPCUAClient run error: {e}")
        finally:
            self._loop.close()

    def start(self, wait_for_startup: bool = True) -> None:
        super().start()
        if wait_for_startup:
            self._wait_for_startup()

    def stop(self, timeout: float = 5.0) -> None:
        self._opcua_status.status = OpcUaClientStatus.STOPPING
        self._aio_stop_event.set()
        try:
            self.join(timeout=timeout)
        except RuntimeError as e:
            log.exception(f"OPCUAClient stop RuntimeError: {e}")
        except KeyboardInterrupt:
            pass
        self._opcua_status.status = OpcUaClientStatus.STOPPED

    def get_client_status(self) -> OpcUaClientStatus:
        return self._opcua_status.status

    # ------------------------------------------------------------------
    # Startup gate  (same pattern as server _wait_for_startup)
    # ------------------------------------------------------------------

    def _wait_for_startup(self) -> None:
        try:
            while True:
                sleep(0.01)
                if self._opcua_status.status in (OpcUaClientStatus.STARTED, OpcUaClientStatus.ERROR):
                        return True
        except KeyboardInterrupt:
            return True

    # ------------------------------------------------------------------
    # Security setup
    # ------------------------------------------------------------------

    async def _setup_security_async(self, client: Client) -> None:
        secure_needed = any( mode in self.config.security_mode.lower() for mode in ["sign", "encrypt"])
        if secure_needed:
            client_cert_path = self._certs_dir / "client_cert.der"
            client_key_path = self._certs_dir / "client_key.pem"

            if not client_cert_path.exists() or not client_key_path.exists():
                log.debug(f"Generating self-signed client certs in {self._certs_dir}")
                await setup_self_signed_certificate(
                    key_file=client_key_path,
                    cert_file=client_cert_path,
                    app_uri=self.config.application_uri,
                    host_name=self.config.hostname,
                    cert_use=[ExtendedKeyUsageOID.CLIENT_AUTH],
                    subject_attrs={"commonName": self.config.client_name},
                )
                log.info("Client certs generated.")

            await client.load_client_certificate(client_cert_path)
            await client.load_private_key(client_key_path)

            if "encrypt" in self.config.security_mode.lower():
                await client.set_security_string(
                    f"Basic256Sha256,SignAndEncrypt,{client_cert_path},{client_key_path}"
                )
            elif "sign" in self.config.security_mode.lower():
                await client.set_security_string(
                    f"Basic256Sha256,Sign,{client_cert_path},{client_key_path}"
                )
        else:
            log.info("No secure policies; skipping certificate setup.")

        # Username/password authentication
        if self.config.users:
            username, password = next(iter(self.config.users.items()))
            client.set_user(username)
            client.set_password(password)

    async def get_available_namespaces(self, namespaces: list[str], client: Client) -> list[str]:
        available_ns: list[str] = []
        for ns in namespaces:
            namespace_idx = await client.get_namespace_index(ns)
            if namespace_idx is not None:
                available_ns.append(f"{ns} (id={namespace_idx})")
        return available_ns


    # ------------------------------------------------------------------
    # Async worker  (reconnect loop + connected loop)
    # ------------------------------------------------------------------

    async def _async_worker(self) -> None:
        while not self._aio_stop_event.is_set():
            try:
                self._opcua_status.status = OpcUaClientStatus.STARTING
                self._client = Client(url=self.config.endpoint)
                self._client.application_uri = self.config.application_uri
                self._client.name = self.config.client_name
                await self._setup_security_async(self._client)
                
                async with self._client as c:
                    server_namespaces = await self._client.get_namespace_array()
                    if self.config.namespace not in server_namespaces:
                        namespace_list = await self.get_available_namespaces(server_namespaces, c)
                        raise NameSpaceMissingError(self.config.namespace, namespace_list)

                    # Resolve namespace URI → index
                    self.namespace_idx = await self._client.get_namespace_index(self.config.namespace)
                    log.info(
                        f"{self.config.client_name} connected:"
                        f"\n  - Endpoint:         {self.config.endpoint}"
                        f"\n  - Namespace URI:    {self.config.namespace} (idx={self.namespace_idx})"
                    )

                    # Fetch nodes and wire subscriptions
                    await self._tag_manager._fetch_tags_async(self._client, self.namespace_idx, self._loop)
                    await self._tag_manager._subscribe_tags_async(self._client, self.config.subscription_poll_period_ms)

                    self._opcua_status.status = OpcUaClientStatus.STARTED

                    # Connected loop
                    while not self._aio_stop_event.is_set():
                        try:
                            await aio.sleep(1)
                            
                            await c.get_node(ua.ObjectIds.Server_ServerStatus_State).read_value()
                        except aio.CancelledError:
                            break
                        except (aio.exceptions.TimeoutError, ConnectionError, Exception) as e:
                            raise DisconnectError(f"Client is disconnected from: '{self.config.endpoint}'")
                            # The 'async with' block will handle closing the transport
                    await self._tag_manager._unsubscribe_async()
            except DisconnectError as e:
                log.error(f"OPCUAClient _async_worker error: {e}")

            except NameSpaceMissingError as e: # possible exception if invalid namespace
                log.error(f"OPCUAClient _async_worker error: {e}")
   
            except Exception as e:
                log.error(f"OPCUAClient _async_worker error: {e}")

            if not self._aio_stop_event.is_set():
                self._opcua_status.status = OpcUaClientStatus.RECONNECTING
                log.info(f"{self.config.client_name} - reconnecting in {self.config.reconnect_interval}s ...")
                await aio.sleep(self.config.reconnect_interval)
            else:
                if self._client and self._client.uaclient.protocol: 
                    await self.tag_manager._subscription.delete()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def client_status(self) -> OpcUaClientStatusClass:
        return self._opcua_status

    @property
    def tag_manager(self) -> ClientTagManager:
        return self._tag_manager
