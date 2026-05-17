"""
easy_opcua - A high-level OPC UA client library for Python
Provides an easy-to-use interface for connecting to OPC UA servers, managing tags, and handling subscriptions
with automatic reconnection support. Built on top of the asyncua library, it abstracts away complexities
while still allowing access to low-level features when needed.

Usage:
    from easy_opcua import OPCUAClient, ClientTagManager, setup_console_logging
    import time

    # Set up logging to see detailed output from the library
    setup_console_logging()

    # Create a tag manager and register tags before connecting
    tag_manager = ClientTagManager()
    tag_manager.add_tag("Temperature", ua.VariantType.Float)
    tag_manager.add_tag("Pressure", ua.VariantType.Float)

    # Define subscription callbacks (optional)
    async def on_temperature_change(data):
        print(f"Temperature changed: {data.value}")

    async def on_pressure_change(data):
        print(f"Pressure changed: {data.value}")

    tag_manager.add_tag_subscriptions({
        "Temperature": on_temperature_change,
        "Pressure": on_pressure_change
    })

    # Create and start the OPC UA client
    config = OpcUaClientConfig(
        server_url="opc.tcp://localhost:4840",
        namespace_uri="http://your-namespace-uri",
        client_name="MyOPCUAClient"
    )
    client = OPCUAClient(config, tag_manager)
    client.start()

    # Wait for the client to connect and fetch tags
    time.sleep(5)

    # Read and write tags using the tag manager
    temp = tag_manager.tags["Temperature"].read()
    print(f"Current Temperature: {temp}")

    tag_manager.tags["Pressure"].write(101.3)

    # Keep the main thread alive to receive subscription updates
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping client...")
        client.stop()
"""
from importlib.metadata import version, PackageNotFoundError
import logging
from logging.handlers import RotatingFileHandler
import sys
import os

try:
    __version__ = version("easy_opcua")
except PackageNotFoundError:
    # If the package isn't installed (e.g. during local dev)
    __version__ = "0.0.0-dev"

class _RelativePathFilter(logging.Filter):
    """Adds %(relpath)s to the log record for clearer traceability."""
    def filter(self, record):
        try:
            record.relpath = os.path.relpath(record.pathname, os.getcwd())
        except (ValueError, AttributeError):
            record.relpath = record.pathname
        return True

# Define the top-level logger for the library.
# All submodules use logging.getLogger(__name__), making them children of this logger.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

def setup_console_logging(level: int = logging.INFO, 
                  format_str: str = '"[%(levelname)-5s] %(name)-20s - %(message)s"') -> logging.Logger:
    """
    Convenience method to configure formatted logging for the library to stdout.
    Call this in the parent application to see detailed logs from easy_opcua.
    """
    # Avoid duplicate handlers if called multiple times
    if any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(format_str))
    logger.addFilter(_RelativePathFilter())
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger

def setup_file_logging(
    filename: str = "easy_opcua.log",
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 5,
    format_str: str = '"%(asctime)s\t[%(levelname)-5s] %(name)-20s - %(message)s"'
) -> logging.Logger:
    """
    Convenience method to configure rotating file logging for the library.
    """
    # Avoid duplicate handlers for the same filename
    abs_filename = os.path.abspath(filename)
    if any(isinstance(h, RotatingFileHandler) and os.path.abspath(h.baseFilename) == abs_filename 
           for h in logger.handlers):
        return logger

    handler = RotatingFileHandler(filename, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(logging.Formatter(format_str))
    
    # Ensure the filter is added
    if not any(isinstance(f, _RelativePathFilter) for f in logger.filters):
        logger.addFilter(_RelativePathFilter())
        
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger

__all__ = ["logger", "setup_console_logging", "setup_file_logging"]