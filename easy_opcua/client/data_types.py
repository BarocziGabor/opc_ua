""" Data types for the OPC UA client """
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Callable, Awaitable
from asyncua import Node
from asyncua.ua import Variant
from asyncua.common.subscription import DataChangeNotif
from easy_opcua import AppLogger

log = AppLogger().get_logger(__name__)



@dataclass
class DataChangeNotifData:
    node: Node
    value: Variant
    data: DataChangeNotif


SyncAndAsyncCallbackType = Callable[[DataChangeNotifData], Awaitable[None] | None]
SyncAndAsyncCallbacks = dict[str, SyncAndAsyncCallbackType]
AddressString = str


class OpcUaClientStatus(StrEnum):
    INIT = auto()
    STARTING = auto()
    STARTED = auto()
    STOPPING = auto()
    STOPPED = auto()
    RECONNECTING = auto()
    ERROR = auto()


class OpcUaClientStatusClass:
    def __init__(self, client_name: str = None):
        self.client_name: str = client_name or "OPC UA Client"
        self._status: OpcUaClientStatus = None
        self._error: Exception = None

    @property
    def status(self) -> OpcUaClientStatus:
        return self._status

    @status.setter
    def status(self, value: OpcUaClientStatus):
        log.info(f"{self.client_name} - {str.capitalize(self._status or 'None')} -> {str.capitalize(value)}")
        self._status = value

    @property
    def error(self) -> Exception:
        return self._error

    @error.setter
    def error(self, value: Exception):
        self._error = value

class NameSpaceMissingError(Exception):
    """Exception raised when the requested namespace URI is not found on the server."""
    def __init__(self, namespace_uri: str, available_namespaces: list[str]):
        self.namespace_uri = namespace_uri
        self.available_namespaces = available_namespaces
        super().__init__(
            f"Namespace URI '{namespace_uri}' not found on server.\n"
            f"Available namespaces: {available_namespaces}")
        
class DisconnectError(Exception):
    """Exception raised when the client is disconnected from the server."""
    def __init__(self, message: str = "Client is disconnected from the OPC UA server"):
        super().__init__(message)

        