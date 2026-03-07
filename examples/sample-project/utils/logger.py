# utils/logger.py — foundation layer
# NOTE: importing from core here is a layer violation (utils → core)
from core import models


def log(message: str) -> None:
    # In a real project, don't do this — this is intentional for demo purposes
    if not isinstance(message, (str, models.Result)):
        raise TypeError("message must be a string")
    print(f"[log] {message}")
