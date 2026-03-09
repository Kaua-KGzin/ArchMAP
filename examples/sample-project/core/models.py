# core/models.py — core domain layer
# NOTE: this creates a circular dependency with core/validators.py
from core import validators


class Result:
    def __init__(self):
        self.valid = validators.validate(self)


class Response:
    def __init__(self, data):
        self.data = data
