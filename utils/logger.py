"""
    Modulo para criação de logs
"""
import logging
from logging.handlers import RotatingFileHandler

# from logging.handlers import RotatingFileHandler

logging.raiseExceptions = False

log = logging.getLogger("")
log.setLevel(logging.DEBUG)

log_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s[%(funcName)s(%(lineno)d)] - %(message)s"
)

# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(log_formatter)
# add the handler to the root logger
log.addHandler(console)

logFile = "discordBot.log"
fileLoggingHandler = RotatingFileHandler(
    logFile,
    mode="a",
    maxBytes=1024 * 100 * 100,  # 10 mb
    backupCount=1,
    encoding=None,
    delay=0,
)
fileLoggingHandler.setFormatter(log_formatter)
fileLoggingHandler.setLevel(logging.DEBUG)
# add the handler to the root logger
log.addHandler(fileLoggingHandler)

if __name__ == "__main__":
    log.log(15, "discord")
    log.info("info")
    log.warning("warn")
    log.debug("debug")
    log.error("error")
    log.critical("critical")
