from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("easy_opcua")
except PackageNotFoundError:
    # If the package isn't installed (e.g. during local dev)
    __version__ = "0.0.0-dev"