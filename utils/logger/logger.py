import os
from datetime import datetime
from enum import IntEnum

class LoggerManager:
    class LOG_LEVELS(IntEnum):
        TRACE = 0
        DEBUG = 1
        INFO = 2
        WARNING = 3
        ERROR = 4
        CRITICAL = 5

    class _Logger:
        def __init__(self, manager, name):
            self._manager = manager
            self._name = name

        def _test_level(self, log_level):
            return self._manager._log_level <= log_level

        def _log(self, message):
            message = f'{datetime.now().isoformat()} - {message}'
            print(f'{self._name}: {message}')

            logpath = os.path.join(self._manager._log_dirpath, f'{self._name}.log')
            with open(logpath, 'a') as f:
                f.write(message + '\n')

        def log_debug(self, message):
            if self._test_level(LoggerManager.LOG_LEVELS.DEBUG):
                self._log(f'DEBUG: {message}')

        def log_info(self, message):
            if self._test_level(LoggerManager.LOG_LEVELS.INFO):
                self._log(f'INFO: {message}')

        def log_warning(self, message):
            if self._test_level(LoggerManager.LOG_LEVELS.WARNING):
                self._log(f'WARNING: {message}')

        def log_error(self, message):
            if self._test_level(LoggerManager.LOG_LEVELS.ERROR):
                self._log(f'ERROR: {message}')

        def log_critical(self, message):
            if self._test_level(LoggerManager.LOG_LEVELS.CRITICAL):
                self._log(f'CRITICAL: {message}')

    def __init__(self):
        self._log_dirpath = None
        self._log_level = None

    def set_log_dirpath(self, log_dirpath):
        try:
            os.makedirs(log_dirpath, exist_ok=True)
            self._log_dirpath = log_dirpath
        except Exception as e:
            raise Exception(f'Failed to create log directory: {e}')

    def set_log_level(self, log_level):
        if not isinstance(log_level, LoggerManager.LOG_LEVELS):
            raise Exception(f'Invalid log level!')

        self._log_level = log_level

    def new_logger(self, name):
        try:
            if self._log_dirpath is None:
                raise Exception(f'Log directory is not set!')

            if self._log_level is None:
                raise Exception(f'Log level is not set!')

            return LoggerManager._Logger(self, name)
        except Exception as e:
            raise Exception(f'Cannot create logger: {e}')

loggerManager = LoggerManager()