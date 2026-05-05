import asyncio as aio
import inspect
from typing import Any 
from asyncua import Node
from asyncua.common.subscription import DataChangeNotif
from .data_types import DataChangeNotifData, SyncAndAsyncCallbackType
import traceback as tb
from easy_opcua import AppLogger

log = AppLogger().get_logger(__name__)



class SubHandler:
    def __init__(self, tag_nodes: list[Node], tag_events: dict[str, SyncAndAsyncCallbackType]):
        self.tag_nodes = tag_nodes
        self.tag_events = tag_events

    async def datachange_notification(self, node: Node, value: Any, data: DataChangeNotif):
        node_id = node.nodeid.Identifier
        if node_id in self.tag_events and value is not None:
            try:
                cb = self.tag_events[node_id]
                if inspect.iscoroutinefunction(cb):
                    await cb(DataChangeNotifData(node, value, data))
                else:
                    loop = aio.get_running_loop()
                    await loop.run_in_executor(None, cb, DataChangeNotifData(node, value, data))
            except Exception as e:
                log.error(f"Error in callback for {node_id}: {e}")
                # tb.print_exc()