from typing import Callable, Any 
from asyncua import Server, ua, Node
from asyncua.common.subscription import Subscription
from .data_types import SyncAndAsyncCallbackType, AddressString
from .subhandler import SubHandler
from .server_tag import ServerTag
from easy_opcua import AppLogger

log = AppLogger().get_logger(__name__)

class TagManager:
    SUBSCRIPTION_POLL_PERIOD_MS = 100
    def __init__(self):
        self.tags: dict[AddressString, ServerTag] = {}
        self._subscription: Subscription = None
        self._tag_subscriptions: dict[AddressString, Callable] = {}
        
    def add_tag(self, address: AddressString, variant_type: ua.VariantType, initial_value: Any = None, writable: bool = True) -> ServerTag:
        tag = ServerTag(address, variant_type, initial_value, writable)
        self.tags[address] = tag
        return tag
        
    def add_tag_subscriptions(self, tag_events: dict[AddressString, SyncAndAsyncCallbackType]):
        for tag_address, callback in tag_events.items():
            if tag_address not in self.tags:
                log.info(f"add_tag_subscription: Tag {tag_address} not found.")
                continue
            # log.info(f"add_tag_subscription: Tag {tag_address} found.")
            self._tag_subscriptions[tag_address] = callback

    async def _subscribe_tags_async(self, opcua_async_server: Server) -> Subscription:
        tag_nodes: list[Node] = []
        for tag_address in self._tag_subscriptions:
            if tag_address not in self.tags or not self.tags[tag_address]._node:
                log.info(f"Warning: Tag {tag_address} not found or not initialized.")
                continue
            tag_nodes.append(self.tags[tag_address]._node)
        if not tag_nodes:
            #  print("TagManager - No valid tags to subscribe to.")
            return None
        
        handler = SubHandler(tag_nodes, self._tag_subscriptions)
        
        self._subscription = await opcua_async_server.create_subscription(self.SUBSCRIPTION_POLL_PERIOD_MS, handler)
        await self._subscription.subscribe_data_change(tag_nodes)
        log.info(f"Created subscription for {len(tag_nodes)} tags")
        return self._subscription

    def read(self, address: AddressString) -> Any | None:
        if address not in self.tags:
            log.info(f"read: Tag {address} not found")
            return None
        return self.tags[address].read()
    
    def write(self, address: AddressString, value: Any) -> bool:
        if address not in self.tags:
            log.info(f"write: Tag {address} not found")
            return False
        self.tags[address].write(value)
        return True
    
    @property
    def tag_list(self) -> list[AddressString]:
        return list(self.tags.keys())

    def __getitem__(self, key: AddressString) -> ServerTag | None:
        return self.read(key)
    
    def __setitem__(self, key: AddressString, value: ServerTag):
        return self.write(key, value)