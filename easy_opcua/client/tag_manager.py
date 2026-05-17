""" ClientTagManager: manages ClientTags and subscriptions on the client side.
Mirrors server-side TagManager but fetches existing nodes instead of creating them.
"""
import asyncio as aio
from typing import Any, Callable
from asyncua import Client, ua, Node
from asyncua.common.subscription import Subscription
from .data_types import SyncAndAsyncCallbackType, AddressString
from .sub_handler import ClientSubHandler
from .client_tag import ClientTag
import logging

log = logging.getLogger(__name__)

class ClientTagManager:
    def __init__(self):
        self.tags: dict[AddressString, ClientTag] = {}
        self._subscription: Subscription = None
        self._tag_events: dict[AddressString, SyncAndAsyncCallbackType] = None

    # ------------------------------------------------------------------
    # Tag registration  (called before connect, defines what to fetch)
    # ------------------------------------------------------------------

    def add_tag(self, address: AddressString, variant_type: ua.VariantType, writable: bool = True, request_timeout: float = 5.0) -> None:
        tag = ClientTag(address, variant_type, writable, request_timeout)
        self.tags[address] = tag

    def add_tag_subscriptions(self, tag_events: dict[AddressString, SyncAndAsyncCallbackType]) -> None:
        """Register datachange callbacks. Must be called before the client connects."""
        self._tag_events = {}
        for tag_address, callback in tag_events.items():
            if tag_address not in self.tags:
                log.warning(f"add_tag_subscriptions: Tag {tag_address} not found.")
                continue
            self._tag_events[tag_address] = callback

    # ------------------------------------------------------------------
    # Async lifecycle  (called by OPCUAClient from within the event loop)
    # ------------------------------------------------------------------

    async def _fetch_tags_async(self, client: Client, namespace_idx: int, loop: aio.AbstractEventLoop) -> None:
        """Resolve each tag address to a live Node and wire up the loop reference."""
        for address, tag in self.tags.items():
            try:
                node_id = ua.NodeId(address, namespace_idx, ua.NodeIdType.String)
                node = client.get_node(node_id)
                tag._set_node(node, loop)
            except Exception as e:
                log.exception(f"_fetch_tags_async: failed to fetch {address}: {e}")

    async def _subscribe_tags_async(self, client: Client, poll_period_ms: int) -> Subscription | None:
        """Create a subscription for all registered tag events."""
        if not self._tag_events:
            return None

        tag_nodes: list[Node] = []
        for tag_address in self._tag_events:
            if tag_address not in self.tags or not self.tags[tag_address]._node:
                log.warning(f"Tag {tag_address} not found or not initialized.")
                continue
            tag_nodes.append(self.tags[tag_address]._node)

        if not tag_nodes:
            log.warning("ClientTagManager - No valid tags to subscribe to.")
            return None

        handler = ClientSubHandler(tag_nodes, self._tag_events)
        self._subscription = await client.create_subscription(poll_period_ms, handler)
        await self._subscription.subscribe_data_change(tag_nodes)
        log.info(f"Created subscription for {len(tag_nodes)} tags")
        return self._subscription

    async def _unsubscribe_async(self) -> None:
        """Delete the active subscription and clear all node references."""
        if self._subscription:
            try:
                await self._subscription.delete()
            except Exception as e:
                log.debug(f"_unsubscribe_async: subscription already gone or session closing: {e}")
            finally:
                self._subscription = None
        for tag in self.tags.values():
            tag._clear_node()

    # ------------------------------------------------------------------
    # Public sync read/write API
    # ------------------------------------------------------------------

    def read(self, address: AddressString) -> Any | None:
        if address not in self.tags:
            log.warning(f"read: Tag {address} not found")
            return None
        return self.tags[address].read()

    def write(self, address: AddressString, value: Any) -> bool:
        if address not in self.tags:
            log.warning(f"write: Tag {address} not found")
            return False
        self.tags[address].write(value)
        return True

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def tag_list(self) -> list[AddressString]:
        return list(self.tags.keys())

    def __getitem__(self, key: AddressString) -> Any | None:
        return self.read(key)

    def __setitem__(self, key: AddressString, value: Any) -> None:
        self.write(key, value)

    def log_tags(self) -> None:
        s = ["ClientTagManager - List of tags:"]
        for tag in self.tags.values():
            s.append(f"  - {tag}")
        log.info("\n".join(s))

    def log_subscriptions(self) -> None:
        s = ["ClientTagManager - List of subscriptions:"]
        for tag_address, callback in self._tag_events.items():
            s.append(f"  - {tag_address}: {callback.__name__}")
        log.info("\n".join(s))