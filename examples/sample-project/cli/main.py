# cli/main.py — entry point layer
from app import service
from app import controller


def run():
    controller.handle(service.process())
