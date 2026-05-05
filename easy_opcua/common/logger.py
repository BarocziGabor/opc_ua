import sys
import logging
from pathlib import Path
from logging import StreamHandler, _levelToName
from logging.handlers import RotatingFileHandler

def get_level_name(level: int) -> str:
    return _levelToName.get(level, "UNKNOWN")

_instance: 'AppLogger' = None

class AppLogger:
    _loggers: dict[str, logging.Logger] = {}
    def __new__(cls, main_logger_name = "main", 
                log_dir: str | Path = "logs",
                logger_level: int = logging.DEBUG,
                streamlog_level: int = logging.NOTSET, 
                streamlog_formatter: str | logging.Formatter = "[%(levelname)-8s] %(name)-20s - %(message)s",
                filelog_level: int = logging.DEBUG,
                filelog_formatter: str | logging.Formatter = "%(asctime)s\t[%(levelname)-8s] %(name)-20s - %(message)s",
                ) -> 'AppLogger':
        global _instance
        if _instance is None:
            _instance = super().__new__(cls)
            cls._mln = main_logger_name
            log_dir = Path(log_dir).resolve()
            log_dir.mkdir(exist_ok=True)
            cls._log_dir = log_dir
            cls._logger_level = logger_level
            cls._streamlog_formatter = streamlog_formatter if isinstance(streamlog_formatter, logging.Formatter) else logging.Formatter(streamlog_formatter)
            cls._filelog_formatter = filelog_formatter if isinstance(filelog_formatter, logging.Formatter) else logging.Formatter(filelog_formatter)
            cls._init_main_logger(streamlog_level, filelog_level)
        return _instance
    
    @classmethod
    def _init_main_logger(cls, streamlog_level: int, filelog_level: int):
        logger = logging.getLogger(cls._mln)
        logger.setLevel(cls._logger_level)
        handlers_enabled = []
        if streamlog_level is not logging.NOTSET:
            sh = StreamHandler(sys.stdout)
            sh.level = streamlog_level
            sh.formatter = cls._streamlog_formatter
            logger.addHandler(sh)
            handlers_enabled.append(f"STREAM: ({get_level_name(sh.level)})")
        if filelog_level is not logging.NOTSET:
            log_path = cls._log_dir / f"{cls._mln}.log"
            rfh = RotatingFileHandler(log_path, maxBytes=10**6, backupCount=3)
            rfh.level = filelog_level
            rfh.formatter = cls._filelog_formatter
            logger.addHandler(rfh)
            handlers_enabled.append(f"FILE: ({get_level_name(rfh.level)})")
        print(f"Init logger {cls._mln} level: {get_level_name(cls._logger_level)} handlers: {', '.join(handlers_enabled)}")
        cls._loggers[cls._mln] = logger
    
    # @classmethod
    # def set_formatter(cls, formatter: str | logging.Formatter = None):
    #     """Set the formatter for all loggers."""
    #     if not isinstance(formatter, logging.Formatter):
    #         formatter = logging.Formatter(formatter)
    #     cls._filelog_formatter = formatter
    #     for logger in cls._loggers.values():
    #         for handler in logger.handlers:
    #             handler.formatter = formatter
    
    # @classmethod
    # def _set_root_logger(cls):
    #     print("setup root logger")
    #     root_logger = logging.getLogger()
    #     sh = logging.StreamHandler(sys.stdout)
    #     sh.level = logging.DEBUG
    #     sh.formatter = logging.Formatter("[%(levelname)s] %(module)s %(lineno)d %(name)s - %(message)s")
    #     root_logger.setLevel(logging.NOTSET)
    #     root_logger.addHandler(sh)
    
    @classmethod
    def get_main_logger(cls) -> logging.Logger:
        logger = logging.getLogger(cls._mln)
        return logger
    
    @classmethod
    def get_logger(cls, name: str, level: int = logging.DEBUG) -> logging.Logger:
        parts = name.split(".")
        if not parts:
            return cls.get_main_logger()
        if cls._mln not in parts:
            parts.insert(0, cls._mln)
        name = ".".join(parts)
        if name in cls._loggers:
            return cls._loggers[name]
        sublogger = logging.getLogger(name)
        sublogger.setLevel(level)
        sublogger.propagate = True
        print(f"Init logger {name} | level: {get_level_name(level)}")
        cls._loggers[name] = sublogger
        return sublogger

    @classmethod    
    def set_level(cls, level: int, logger_name: str = None):
        """Set the logging level for a specific logger or the main logger."""
        target = logger_name if logger_name else cls._mln
        if target in cls._loggers:
            cls._loggers[target].setLevel(level)
            print(f"Logger {target} level set to {get_level_name(level)}")
        else:
            print(f"Logger {target} not found.")

    @classmethod
    def list_loggers(cls):
        """List all loggers."""
        print("Loggers:")
        for name, logger in cls._loggers.items():
            print(f" - {name}: {get_level_name(logger.level)}")


if __name__ == "__main__":
    logger = AppLogger(streamlog_level=logging.DEBUG, filelog_level=logging.NOTSET)   
    opcualogger = logger.get_logger("main.opcua") 
    opcualogger.debug("asd")
    mainlogger = logger.get_main_logger()
    mainlogger.debug("asd")
    logger.list_loggers()
    mainlogger.setLevel(logging.INFO)
    mainlogger.debug("asd2")
    opcualogger.setLevel(logging.INFO)
    opcualogger.debug("dsa2")
    logger.list_loggers()
