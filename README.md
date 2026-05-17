# easy_opcua

`easy_opcua` is a high-level Python wrapper around `asyncua` designed to simplify OPC UA integration. It manages the complexities of asynchronous loops, automatic reconnections, and thread-safe operations, allowing you to focus on data handling.

## Features

- **Threaded Execution**: Both Client and Server run in their own dedicated threads.
- **Automatic Reconnection**: The client automatically attempts to reconnect and re-subscribe to tags if the connection drops.
- **Thread-Safe API**: Read and write tags using simple synchronous methods from your main application thread.
- **Configurable Logging**: Built-in utilities to format and pipe library logs to the console or rotating files.

---

## Logging Setup

By default, the library is silent. You can enable pre-configured logging with a single line to see what's happening inside the library (connections, subscriptions, errors).

```python
from easy_opcua import setup_console_logging, setup_file_logging
import logging

# 1. Quick console logs with a clean format
setup_console_logging(level=logging.INFO)

# 2. Optional: Log to a rotating file for debugging production issues
setup_file_logging(
    filename="opcua_debug.log",
    max_bytes=5*1024*1024, # 5MB
    backup_count=3
)
```

---

## Client Example

The `OPCUAClient` uses a `ClientTagManager` to handle node resolution and data change subscriptions.

```python
import time
from easy_opcua import OPCUAClient, ClientTagManager, setup_console_logging
from easy_opcua.client.client_config import OpcUaClientConfig
from asyncua import ua

setup_console_logging()

# 1. Define callbacks for subscriptions
def on_temp_change(data):
    print(f"Subscription Update - {data.node}: {data.value}")

# 2. Setup Tag Manager and register tags
tag_manager = ClientTagManager()
tag_manager.add_tag("Sensors.Temperature", ua.VariantType.Float)
tag_manager.add_tag_subscriptions({"Sensors.Temperature": on_temp_change})

# 3. Configure and Start Client
config = OpcUaClientConfig(
    endpoint="opc.tcp://localhost:4840",
    namespace="http://example.org/",
    client_name="MyClient"
)

client = OPCUAClient(config, tag_manager)
client.start() # Starts the internal thread and event loop

# 4. Use the thread-safe API
try:
    while True:
        # Synchronous read
        val = tag_manager.read("Sensors.Temperature")
        print(f"Polled Value: {val}")
        
        # Synchronous write
        tag_manager.write("Sensors.Temperature", 25.5)
        time.sleep(5)
except KeyboardInterrupt:
    client.stop()
```

---

## Server Example

The `OPCUAServer` allows you to host tags and handle user authentication easily.

```python
from easy_opcua.server.server import OPCUAServer
from easy_opcua.server.server_config import OpcUaServerConfig
from easy_opcua.server.tag_manager import TagManager
from asyncua import ua
import time

# 1. Setup Tags
tag_manager = TagManager()
tag_manager.add_tag("Sensors.Temperature", ua.VariantType.Float, initial_value=20.0, writable=True)

# 2. Configure Server
config = OpcUaServerConfig(
    endpoint="opc.tcp://0.0.0.0:4840",
    server_name="MyOPCUAServer",
    namespace="http://example.org/",
    users={"admin": "password123"} # Enable user/pass auth
)

# 3. Start Server
server = OPCUAServer(config, tag_manager)
server.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    server.stop()
```