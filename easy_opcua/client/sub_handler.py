""" ClientSubHandler: handles datachange notifications from the OPC UA server.
Identical in structure to the server-side SubHandler — callback dispatch
is direction-agnostic (server push → client callback).
"""
import asyncio as aio
import inspect
import traceback as tb
from typing import Any
from asyncua import Node
from asyncua.ua import StatusChangeNotification
from asyncua.common.subscription import DataChangeNotif
from .data_types import DataChangeNotifData, SyncAndAsyncCallbackType
from easy_opcua import AppLogger

log = AppLogger().get_logger(__name__)


class ClientSubHandler:
    def __init__(self, tag_nodes: list[Node], tag_events: dict[str, SyncAndAsyncCallbackType]):
        self.tag_nodes = tag_nodes
        self.tag_events = tag_events

    async def datachange_notification(self, node: Node, value: Any, data: DataChangeNotif) -> None:
        node_id = node.nodeid.Identifier
        if node_id in self.tag_events and value is not None:
            try:
                cb = self.tag_events[node_id]
                notif = DataChangeNotifData(node, value, data)
                if inspect.iscoroutinefunction(cb):
                    await cb(notif)
                else:
                    loop = aio.get_running_loop()
                    await loop.run_in_executor(None, cb, notif)
            except Exception as e:
                log.exception(f"ClientSubHandler error in callback for {node_id}: {e}")

    def status_change_notification(self, status: StatusChangeNotification):
        ...
