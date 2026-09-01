"""Data repository package."""

from app.repositories.base import DataRepository
from app.repositories.json_repository import JsonDataRepository

__all__ = ["DataRepository", "JsonDataRepository"]
