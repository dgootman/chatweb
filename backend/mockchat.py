import random
from datetime import datetime

import aiohttp

from model import (
    ChatProvider,
    ChatProviderInfo,
    Contact,
    Conversation,
    Message,
    SendMessage,
)


class MockChatProvider(ChatProvider):
    def __init__(self) -> None:
        super().__init__()
        self._me: Contact = None
        self._contacts: list[Contact] = []
        self._conversations: list[Conversation] = []
        self._messages: dict[str, list[Message]] = {}

    def info(self) -> ChatProviderInfo:
        return ChatProviderInfo(
            id="mock",
            name="Mock",
            icon="https://em-content.zobj.net/source/apple/354/speech-balloon_1f4ac.png",
        )

    async def init(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://randomuser.me/api/?results=11") as response:
                data = await response.json()

                all_contacts = [
                    Contact(
                        id=result["login"]["uuid"],
                        name=f"""{result["name"]["first"]} {result["name"]["last"]}""",
                        avatar=result["picture"]["thumbnail"],
                    )
                    for result in data["results"]
                ]
                self._me = all_contacts[0]
                self._contacts = all_contacts[1:]

        self._conversations = [
            Conversation(**contact.model_dump()) for contact in await self.contacts()
        ]

        async def get_messages(conversation_id: str):
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://baconipsum.com/api/?type=meat-and-filler"
                ) as response:
                    return [
                        Message(
                            timestamp=datetime.now(),
                            body=bacon,
                            sender=random.choice([conversation_id, self._me.id]),
                        )
                        for bacon in await response.json()
                    ]

        self._messages = {
            conversation.id: await get_messages(conversation.id)
            for conversation in self._conversations
        }

    async def whoami(self) -> Contact:
        return self._me

    async def contacts(self) -> list[Contact]:
        return self._contacts

    async def conversations(self) -> list[Conversation]:
        return self._conversations

    async def messages(self, conversation_id: str) -> list[Message]:
        return self._messages[conversation_id]

    async def send_message(self, request: SendMessage) -> None:
        self._messages[request.conversation_id].append(
            Message(timestamp=datetime.now(), body=request.body, sender=self._me.id)
        )
