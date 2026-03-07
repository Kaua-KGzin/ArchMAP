# core/validators.py — core domain layer
# NOTE: imports models creates a circular dependency
from core import models
from utils import logger


def validate(obj):
    logger.log(f"validating {obj}")
    return isinstance(obj, (models.Result, dict))
