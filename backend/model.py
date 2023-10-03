from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class Contact(BaseModel):
    id: str
    name: str
    avatar: str


class Conversation(BaseModel):
    id: str
    name: str
    avatar: str
    last_active: datetime = None


class Message(BaseModel):
    timestamp: datetime
    body: str | None
    sender: str


class SendMessage(BaseModel):
    conversation_id: str
    body: str


class ChatProvider(ABC):
    @abstractmethod
    async def init(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def whoami(self) -> Contact:
        raise NotImplementedError()

    @abstractmethod
    async def contacts(self) -> list[Contact]:
        raise NotImplementedError()

    @abstractmethod
    async def conversations(self) -> list[Conversation]:
        raise NotImplementedError()

    @abstractmethod
    async def messages(self, conversation_id: str) -> list[Message]:
        raise NotImplementedError()

    @abstractmethod
    async def send_message(self, request: SendMessage) -> None:
        raise NotImplementedError()
