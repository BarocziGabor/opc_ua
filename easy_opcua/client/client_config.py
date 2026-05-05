""" Pydantic config model for the OPC UA client """
from pydantic import BaseModel
from typing import Dict

class OpcUaClientConfig(BaseModel):
    endpoint: str                           # e.g. "opc.tcp://localhost:4840/freeopcua/server/"
    namespace: str                          # namespace URI, resolved to index at connect time
    client_name: str = "OPC UA Client"
    security_mode: str = "none"            # "none", "sign", "encrypt", or combinations
    users: Dict[str, str] | None = None    # {"username": "password"}
    hostname: str = "localhost"
    reconnect_interval: float = 5.0        # seconds between reconnect attempts
    subscription_poll_period_ms: int = 100  # subscription publishing interval
    request_timeout: float = 5.0           # seconds for sync read/write calls
    application_uri: str = "urn:asyncua:python:client"
