from easy_opcua.common.logger import AppLogger, logging

easy_opcua_logger = AppLogger("easy_opcua", filelog_level=logging.warning, streamlog_level=logging.warning)

__all__ = ["easy_opcua_logger"]