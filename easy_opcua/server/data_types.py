from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Callable, Awaitable
from asyncua import ua, Node
from asyncua.ua import Variant, VariantType 
from asyncua.common.node import Node
from asyncua.common.subscription import DataChangeNotif
import logging

log = logging.getLogger(__name__)

@dataclass
class DataChangeNotifData:
    node: Node
    value: Variant
    data: DataChangeNotif

SyncAndAsyncCallbackType = Callable[[DataChangeNotifData], Awaitable[None] | None]
SyncAndAsyncCallbacks = dict[str, SyncAndAsyncCallbackType]
AddressString = str
 
class OpcUaServerStatus(StrEnum):
    INIT = auto()
    STARTING = auto()
    STARTED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()

class OpcUaServerStatusClass:
    def __init__(self, server_name: str = None):
        self.server_name: str = server_name or "OPC UA Server"
        self._status: OpcUaServerStatus = None
        self._error: Exception = None
    
    @property
    def status(self) -> OpcUaServerStatus:
        return self._status
    
    @status.setter
    def status(self, value: OpcUaServerStatus):
        log.info(f"{self.server_name} - {str.capitalize(self._status or "None")} -> {str.capitalize(value)}")
        self._status = value
        
    @property
    def error(self):
        return self._error
    
    @error.setter
    def error(self, value: Exception):
        self._error = value