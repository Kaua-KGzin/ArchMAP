# app/service.py — application layer
from core import models
from core import validators
from utils import logger


def process():
    logger.log("processing")
    validators.validate({})
    return models.Result()
