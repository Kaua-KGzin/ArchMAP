# app/controller.py — application layer
from core import models
from utils import logger


def handle(result):
    logger.log(f"handling {result}")
    return models.Response(result)
