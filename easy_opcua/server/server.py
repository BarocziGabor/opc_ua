import asyncio as aio
from time import sleep
from threading import Thread
from typing import Any, Optional, Tuple
from pathlib import Path
from asyncua import Server, ua, Node
from asyncua.server.internal_server import InternalServer
from asyncua.ua import SecurityPolicyType
from asyncua.server.user_managers import UserManager, User, UserRole
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.server.internal_session import InternalSession
from asyncua.common.event_objects import AuditActivateSessionEvent, AuditSessionEvent
from cryptography.x509.oid import ExtendedKeyUsageOID
from .data_types import OpcUaServerStatus, OpcUaServerStatusClass, AddressString
from .server_config import OpcUaServerConfig
from .tag_manager import TagManager
import traceback as tb
import logging

log = logging.getLogger(__name__)

class MyUserManager(UserManager):
    def __init__(self, config: OpcUaServerConfig):
        log.debug("MyUserManager initialized")
        self.config = config

    def get_user(self, iserver: InternalServer, username=None, password=None, certificate=None):
        """
        Called on ActivateSession — i.e. every client "connect".
        iserver  : InternalServer instance
        username : str or None (anonymous → None)
        password : str or None
        certificate : cert object or None
        Return User(...) to allow, or None to reject.
        """
        if username and iserver.allow_remote_admin and username in ("admin", "Admin"):
            log.info(f"CONNECT user='{username}' (Admin)")
            return User(role=UserRole.Admin, name=username)
        elif username and username in self.config.users:
            log.info(f"CONNECT user='{username}'")
            return User(role=UserRole.User, name=username)
        else:
            log.info("CONNECT anonymous")
            return User(role=UserRole.Anonymous)

class MySession(InternalSession):
    async def create_session(self, params: ua.CreateSessionParameters, sockname: Optional[Tuple[str, int]] = None):
        self.logger.info(f"create_session: {str(params.SessionName)}")
        return await super().create_session(params, sockname)


    def activate_session(self, params, peer_certificate):
        result = super().activate_session(params, peer_certificate)
        username = getattr(self.user, "name", None) or "anonymous"
        # print(f"CONNECT  user='{username}'  session='{self.name}'")
        return result

    async def close_session(self, delete_subscriptions: bool):
        username = getattr(self.user, "name", None) or "anonymous"
        log.info(f"DISCONNECT user='{username}' session='{self.name}'")
        await super().close_session(delete_subscriptions)

class MyInternalServer(InternalServer):
    def create_session(self, name, user: User = None, external=False):
        session = MySession(self, self.aspace, self.subscription_service, name, user, external)
        # self.sessions[session.session_id] = session
        return session
    
class OPCUAServer(Thread):
    """ OPCUAServer class that runs an asynchronous OPC UA server in a separate thread.
    It manages node creation, folder hierarchy, and tag subscriptions via a TagManager.
    """
    def __init__(self, config: OpcUaServerConfig, tag_manager: TagManager = None, certs_dir: str = None):
        """Initialize the OPCUAServer.

        Args:
            config (OpcUaServerConfig): _description_
            tag_manager (TagManager, optional): _description_. Defaults to None.

        """
        super().__init__(name=config.server_name, daemon=True)
        self._certs_dir = Path.cwd() / "certs" if not certs_dir else certs_dir
        self._certs_dir.mkdir(exist_ok=True)
        self.config = config
        self._tag_manager = tag_manager
        self._opcua_status = OpcUaServerStatusClass(config.server_name)
        self._aio_stop_event = aio.Event()
        self._server: Server = None
        self._folder_nodes: dict[ua.NodeId, Node] = {}


    def run(self):
        """Overwrite generic run for in new thread"""
        self._loop = aio.new_event_loop()
        aio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_worker())
        except Exception as e:
            log.exception(f"OPCUAServer run error: {e}")
            pass
        finally:
            self._loop.close()
        
        
    def start(self, wait_for_startup: bool = True):
        super().start()
        if wait_for_startup:
            self._wait_for_startup()
    
    def stop(self, timeout: int = 5):
        self._opcua_status.status = OpcUaServerStatus.STOPPING
        self._aio_stop_event.set()
        try:
            self.join(timeout)
        except RuntimeError as e:
            log.error(f"OPCUAServer stop RuntimeError: {e}")
        except TimeoutError as e:
            log.error(f"OPCUAServer stop TimeoutError: {e}")
        except KeyboardInterrupt:
            pass
        self._opcua_status.status = OpcUaServerStatus.STOPPED 
    
    @property        
    def server_status(self) -> OpcUaServerStatus:
        return self._opcua_status.status
    
    def _wait_for_startup(self) -> bool:
        try:
            while True:
                sleep(0.01)
                if self._opcua_status.status == OpcUaServerStatus.STARTED or self._opcua_status.status == OpcUaServerStatus.ERROR:
                    return True
        except KeyboardInterrupt:
            return True
    
    async def _register_tags_async(self):
        for tag in self._tag_manager.tags.values():
            node = await self._create_node_with_folder_hierarchy(tag._address, tag._variant_type, tag._initial_value, tag._writable)
            tag._set_node(node, self._loop)
        
    async def _create_node_with_folder_hierarchy(self, tag_address: AddressString, variant_type: ua.VariantType, initial_value: Any = None, writable: bool = False) -> Node:       
        parts = tag_address.split(".")
        tag_name = parts[-1]
        folder_path = parts[:-1]     
        current_node = self._server.get_objects_node()
        for i, folder_name in enumerate(folder_path):
            folder_browse_path = '.'.join(folder_path[:i+1])
            folder_nodeid = ua.NodeId(folder_browse_path, self.namespace_idx, ua.NodeIdType.String)
            # Check if folder already exists in tags
            folder_exists = False
            for _folder_nodeid, folder_node in self._folder_nodes.items():
                if folder_nodeid == _folder_nodeid:
                    current_node = folder_node
                    folder_exists = True
                    break

            if not folder_exists:
                # Create folder
                folder_node = await current_node.add_folder(folder_nodeid, folder_name)
                self._folder_nodes[folder_nodeid] = folder_node
                current_node = folder_node

        # Create variable node
        tag_nodeid = ua.NodeId(tag_address, self.namespace_idx, ua.NodeIdType.String)
        var_node = await current_node.add_variable(tag_nodeid, tag_name, initial_value if initial_value else ua.get_default_value(variant_type), variant_type)

        # Set writable attribute
        if writable and not self.config.disable_write:
            await var_node.set_writable()
        return var_node
    
    async def _setup_security_async(self):
        secure_needed = any(mode in self.config.security_mode.lower() for mode in ["sign", "encrypt"])
        if secure_needed:
            server_cert_path = self._certs_dir / "server_cert.der"
            server_key_path  = self._certs_dir / "server_key.pem"

            if not server_cert_path.exists() or not server_key_path.exists():
                log.info(f"Generating self-signed certs in {self._certs_dir}")
                await setup_self_signed_certificate(
                    key_file=server_key_path,
                    cert_file=server_cert_path,
                    # app_uri=f"urn:{self.config.server_name}:OPCUAServer",
                    app_uri=f"urn:freeopcua:python:server",
                    host_name=self.config.hostname,          # e.g. "localhost" or machine hostname
                    cert_use=[ExtendedKeyUsageOID.SERVER_AUTH],
                    subject_attrs={"commonName": self.config.server_name}
                )
                log.info("Certs generated.")

            await self._server.load_certificate(server_cert_path)
            await self._server.load_private_key(server_key_path)
        else:
            log.info("No secure policies; skipping certificate setup.")


        # Security policies
        policies: list[SecurityPolicyType] = []
        if "none" in self.config.security_mode.lower():
            policies.append(SecurityPolicyType.NoSecurity)
        if "sign" in self.config.security_mode.lower():
            policies.append(SecurityPolicyType.Basic256Sha256_Sign)
        if "encrypt" in self.config.security_mode.lower():
            policies.append(SecurityPolicyType.Basic256Sha256_SignAndEncrypt)
        self._server.set_security_policy(policies)

        # User token policies
        tokens = [ua.AnonymousIdentityToken]
        if self.config.users:
            tokens.append(ua.UserNameIdentityToken)
            log.info(f"User token policy enabled with {len(self.config.users)} users.")

        self._server.set_identity_tokens(tokens)
        
    async def _async_worker(self):
        """Example usage of the OPC UA Server"""
        if self.config.enabled is False:
            log.warning("OPC UA Server is disabled in configuration.")
            return
        self._opcua_status.status = OpcUaServerStatus.STARTING
        # self._server = Server(iserver=MyInternalServer(MyUserManager(self.config)))
        self._server = Server()
        await self._server.init()
        cfg = self.config
        self._server.set_endpoint(cfg.endpoint)
        self._server.set_server_name(cfg.server_name)
        await self._setup_security_async()
        # Setup namespace
        self.namespace_idx = await self._server.register_namespace(cfg.namespace)
        if self._tag_manager:
            await self._register_tags_async()
            await self._tag_manager._subscribe_tags_async(self._server)
        else:
            log.info("No tags to subscribe to.")

        try:
            async with self._server:
                log.info(f"{self.config.server_name} started:")
                log.info(f"  - Server name: {cfg.server_name}")
                log.info(f"  - Endpoint: {cfg.endpoint}")
                log.info(f"  - Namespace index: {cfg.namespace} (idx={self.namespace_idx})")
                log.info(f"  - Global writing enabled: {not self.config.disable_write}")
                if self._tag_manager:
                    log.info(f"  - Tags: {len(self._tag_manager.tag_list)}") if self._tag_manager.tag_list else ...
                    log.info(f"  - Subscriptions: {len(self._tag_manager._tag_subscriptions)}") if self._tag_manager._tag_subscriptions else ...
                self._opcua_status.status = OpcUaServerStatus.STARTED
                while not self._aio_stop_event.is_set():
                    try:
                        await aio.sleep(0.1)
                    except aio.TimeoutError:
                        continue  # No item in queue, just loop again
                    except Exception as e:
                        log.error(f"Error processing queue item: {e}")
                        await aio.sleep(0.1)
        except PermissionError as e:
            log.error(f"OPCUAServer Unable to bind to endpoint: {cfg.endpoint}. Permission denied.")
            self._opcua_status.status = OpcUaServerStatus.ERROR
            self._opcua_status.error = e
        except Exception as e:
            log.error(f"OPCUAServer _async_worker error: {e}")
            self._opcua_status.status = OpcUaServerStatus.ERROR
            self._opcua_status.error = e
