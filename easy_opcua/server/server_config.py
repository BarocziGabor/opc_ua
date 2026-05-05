from pydantic import BaseModel, field_validator
from typing import Dict
Username = str
Password = str

class OpcUaServerConfig(BaseModel):
    endpoint: str = "opc.tcp://localhost:4888"
    namespace: str = "urn:freeopcua:python:server"
    server_name: str = "OPC UA Server"
    enabled: bool = True
    disable_write: bool = False
    security_mode: str = "none"
    users: Dict[Username, Password] | None = None
    hostname: str = "localhost"

    @field_validator("endpoint", mode="before")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Automatically correct common typos or missing protocols in the OPC UA endpoint string."""
        if not isinstance(v, str):
            return v
        
        if v.startswith("opc.tcp://"):
            return v
        elif v.startswith("opc.tcp:/"):
            return v.replace("opc.tcp:/", "opc.tcp://", 1)
        elif not v.startswith("opc.tcp:"):
            return f"opc.tcp://{v}"
        return v