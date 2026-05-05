import asyncio as aio
from typing import Any 
from asyncua import ua, Node
from asyncua.ua import Variant
from asyncua.common.node import Node
from easy_opcua import AppLogger

log = AppLogger().get_logger(__name__)


class ServerTag:
    def __init__(self, address: str, variant_type: ua.VariantType, initial_value: Any = None, writable: bool = False):
        self._node: Node = None
        self._address: str = address
        self._writable: bool = None
        self._variant_type: ua.VariantType = variant_type
        self._initial_value: Any = initial_value
        self._writable: bool = writable
        self._loop: aio.AbstractEventLoop = None

    def read(self) -> Any:
        if not self._node:
            log.warning(f"Tag {self._address} not initialized")
            return None
        try:
            future = aio.run_coroutine_threadsafe(self._read_async(), self._loop)
            return future.result(timeout=5)
        except Exception:
            log.exception(f"Tag {self._address} read error")
    
    def write(self, value):
        if not self._node:
            log.warning(f"Tag {self._address} not initialized")
            return
        try:
            future = aio.run_coroutine_threadsafe(self._write_async(Variant(value, self._variant_type)), self._loop)
            future.result(timeout=5)
        except Exception:
            log.exception(f"Tag {self._address} write error")
        
    async def _read_async(self) -> Any:
        if not self._node:
            log.warning(f"Tag {self._address} not initialized")
            return
        return await self._node.read_value()

    async def _write_async(self, value: Variant):
        if not self._node:
            log.warning(f"Tag {self._address} not initialized")
            return
        await self._node.write_value(value, self._variant_type)

    def _set_node(self, node: Node, loop: aio.AbstractEventLoop):
        self._node = node
        self._loop = loop