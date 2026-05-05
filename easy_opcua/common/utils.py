from time import perf_counter
import logging
import sys
import os

class Timeit:
    global_enable = True
    newline = True
    timeit_objects = {}
    
    def __init__(self, name: str) -> None:
        self.name = name
        
    def __enter__(self):
        self.start = perf_counter()
        self.timeit_objects[self.name] = 0.0
        self.msg = ""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        delta = perf_counter() - self.start
        self.timeit_objects[self.name] = delta
        msg = f" Msg: {self.msg}" if self.msg else ""
        if self.global_enable:
            print(f"{self.name}: {delta:.5f} seconds{msg}", end="\n" if self.newline else "\r")

def set_stdout_for_logger(logger_name: str, 
                          level: int = logging.DEBUG, 
                          format_str: str = '[%(levelname)-8s] "%(relpath)s", line %(lineno)-4d - %(message)s'):
    class RelativePathFilter(logging.Filter):
        """Adds %(relpath)s to the log record."""
        def filter(self, record):
            # Calculates path relative to the current working directory
            record.relpath = os.path.relpath(record.pathname, os.getcwd())
            return True
    if not logger_exsist(logger_name):
        print(f"Logger does not exists: {logger_name} cannot set stdout")
        return
    logger = logging.getLogger(logger_name)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    if format_str:        
        stream_handler.setFormatter(logging.Formatter(format_str))
    logger.addHandler(stream_handler)
    logger.setLevel(level)
    logger.addFilter(RelativePathFilter())
    
def list_loggers():
    loggers = [logging.getLogger()]  # get the root logger
    loggers = loggers + [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    print("\n".join(map(str, loggers)))

def logger_exsist(logger_name: str) -> bool:
    return logger_name in logging.root.manager.loggerDict