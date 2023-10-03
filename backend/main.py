import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header
from loguru import logger

from keybase import KeybaseChatProvider
from mockchat import MockChatProvider
from model import ChatProvider, SendMessage

load_dotenv()


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

_providers: list[ChatProvider] = [KeybaseChatProvider(), MockChatProvider()]
_providers_map = {provider.info().id: provider for provider in _providers}


def get_provider(provider_id: Annotated[str, Header()]):
    return _providers_map[provider_id]


ChatProviderDependency = Annotated[ChatProvider, Depends(get_provider)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Initialize all providers
    await asyncio.gather(*list(p.init() for p in _providers))

    yield


app = FastAPI(lifespan=lifespan)


@app.get("/providers")
async def providers():
    return [p.info() for p in _providers]


@app.get("/whoami")
async def whoami(provider: ChatProviderDependency):
    return await provider.whoami()


@app.get("/contacts")
async def contacts(provider: ChatProviderDependency):
    return await provider.contacts()


@app.get("/conversations")
async def conversations(provider: ChatProviderDependency):
    return await provider.conversations()


@app.get("/messages")
async def messages(
    provider: ChatProviderDependency,
    conversation_id: str,
):
    return await provider.messages(conversation_id)


@app.post("/messages")
async def send_message(provider: ChatProviderDependency, request: SendMessage):
    return await provider.send_message(request)
