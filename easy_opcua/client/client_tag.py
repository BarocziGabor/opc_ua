""" ClientTag: wraps a single OPC UA node on the client side.
Mirrors server-side Tag but fetches existing nodes rather than creating them.
All sync read/write calls are thread-safe via run_coroutine_threadsafe.
"""
import asyncio as aio
from typing import Any
from asyncua import ua, Node
from asyncua.ua import Variant
from .data_types import AddressString
import logging

log = logging.getLogger(__name__)

class ClientTag:
    def __init__(
        self,
        address: AddressString,
        variant_type: ua.VariantType,
        writable: bool = True,
        request_timeout: float = 5.0,
    ):
        self._address: AddressString = address
        self._variant_type: ua.VariantType = variant_type
        self._writable: bool = writable
        self._request_timeout: float = request_timeout
        self._node: Node = None
        self._loop: aio.AbstractEventLoop = None

    # ------------------------------------------------------------------
    # Public sync API  (safe to call from any external thread)
    # ------------------------------------------------------------------

    def read(self) -> Any:
        """Synchronously read the tag value from the OPC UA server.
        Thread-safe: delegates to the client's running event loop."""
        if not self._is_ready():
            return None
        future = aio.run_coroutine_threadsafe(self._read_async(), self._loop)
        return future.result(timeout=self._request_timeout)

    def write(self, value: Any) -> None:
        """Synchronously write a value to the OPC UA server.
        Thread-safe: delegates to the client's running event loop."""
        if not self._is_ready():
            return
        if not self._writable:
            log.warning(f"{self._address} is not marked writable")
            return
        future = aio.run_coroutine_threadsafe(
            self._write_async(Variant(value, self._variant_type)), self._loop
        )
        future.result(timeout=self._request_timeout)

    # ------------------------------------------------------------------
    # Public async API  (safe to await inside the client's event loop)
    # ------------------------------------------------------------------

    async def read_async(self) -> Any:
        return await self._read_async()

    async def write_async(self, value: Any) -> None:
        if not self._writable:
            log.warning(f"ClientTag {self._address} is not marked writable")
            return
        await self._write_async(Variant(value, self._variant_type))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _read_async(self) -> Any:
        if not self._node:
            log.warning(f"ClientTag {self._address} not initialized")
            return None
        return await self._node.read_value()

    async def _write_async(self, value: Variant) -> None:
        if not self._node:
            log.warning(f"{self._address} not initialized")
            return
        await self._node.write_value(ua.DataValue(value))

    def _set_node(self, node: Node, loop: aio.AbstractEventLoop) -> None:
        """Called by ClientTagManager once the node has been fetched from the server."""
        self._node = node
        self._loop = loop

    def _clear_node(self) -> None:
        """Called on disconnect to invalidate the node reference."""
        self._node = None
        self._loop = None

    def _is_ready(self) -> bool:
        if not self._node or not self._loop:
            log.warning(f"{self._address} not initialized")
            return False
        return True

    def __repr__(self) -> str:
        return f"ClientTag(address={self._address}, type={self._variant_type}, writable={self._writable})"
