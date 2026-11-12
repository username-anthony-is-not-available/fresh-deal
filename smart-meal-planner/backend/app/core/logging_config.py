import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.secrets import SecretRedactionFilter


def setup_logging():
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    handler.setFormatter(formatter)
    handler.addFilter(SecretRedactionFilter())
    log.addHandler(handler)
