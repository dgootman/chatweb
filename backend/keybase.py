import asyncio
import json
import os
from datetime import datetime
from enum import Enum

import aiohttp
from loguru import logger
from pydantic import BaseModel
from slugify import slugify

from model import (
    ChatProvider,
    ChatProviderInfo,
    Contact,
    Conversation,
    Message,
    SendMessage,
)


class WhoamiResponse(BaseModel):
    class User(BaseModel):
        uid: str
        username: str

    user: User


class ListMembersResponse(BaseModel):
    class Result(BaseModel):
        class Owner(BaseModel):
            uid: str
            username: str
            fullName: str | None

        owners: list[Owner]

    result: Result


class ListResponse(BaseModel):
    class Result(BaseModel):
        class Conversation(BaseModel):
            class Channel(BaseModel):
                class MemberType(str, Enum):
                    # pylint: disable=invalid-name
                    impteamnative = "impteamnative"
                    team = "team"

                name: str
                members_type: MemberType

            id: str
            channel: Channel
            active_at: int
            active_at_ms: int

        conversations: list[Conversation]

    result: Result


class ReadResponse(BaseModel):
    class Result(BaseModel):
        class KeybaseMessage(BaseModel):
            class KeybaseMsg(BaseModel):
                class KeybaseContent(BaseModel):
                    class KeybaseText(BaseModel):
                        body: str

                    type: str
                    text: KeybaseText | None

                class KeybaseSender(BaseModel):
                    uid: str

                id: str
                sender: KeybaseSender
                sent_at: int
                content: KeybaseContent

            msg: KeybaseMsg

        messages: list[KeybaseMessage]

    result: Result


class KeybaseChatProvider(ChatProvider):
    def __init__(self) -> None:
        self.keybase_command = os.environ.get("KEYBASE_COMMAND", "keybase")

    def info(self) -> ChatProviderInfo:
        return ChatProviderInfo(
            id="keybase",
            name="Keybase",
            icon="https://keybase.io/images/icons/icon-keybase-logo-48@2x.png",
        )

    async def run(self, command: list[str]):
        full_command = self.keybase_command.split() + command
        logger.debug(f"Keybase command: {full_command}")

        process = await asyncio.create_subprocess_exec(
            full_command[0],
            *full_command[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if await process.wait() != 0:
            raise RuntimeError(
                "\n\t".join(
                    (
                        "Keybase command failed:",
                        f"Code: {process.returncode}",
                        f"Output: {(await process.stdout.read()).decode()}",
                        f"Error: {(await process.stderr.read()).decode()}",
                    )
                )
            )

        result = await process.stdout.read()
        result = result.decode()
        logger.debug(f"Keybase result: {result}")
        return result

    async def chat(self, command: dict) -> dict:
        result = await self.run(
            [
                "chat",
                "api",
                "-m",
                json.dumps(command),
            ]
        )
        return json.loads(result)

    async def init(self) -> None:
        pass

    async def whoami(self) -> Contact:
        data = await self.run("whoami -j".split())
        response = WhoamiResponse(**json.loads(data))
        return Contact(
            id=response.user.uid,
            name=response.user.username,
            avatar=f"https://api.dicebear.com/7.x/initials/svg?seed={slugify(response.user.username)}",
        )

    async def list_members(self, conversation_id: str) -> ListMembersResponse:
        data = await self.chat(
            {
                "method": "listmembers",
                "params": {"options": {"conversation_id": conversation_id}},
            }
        )
        return ListMembersResponse(**data)

    async def contacts(self) -> list[Contact]:
        data = await self.chat({"method": "list"})
        list_response = ListResponse(**data)
        conversations = list_response.result.conversations

        conversation_members_list = await asyncio.gather(
            *[self.list_members(c.id) for c in conversations]
        )

        owners = {o.uid: o for r in conversation_members_list for o in r.result.owners}

        usernames = ",".join(o.username for o in owners.values())
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://keybase.io/_/api/1.0/user/lookup.json?usernames={usernames}&fields=basics,pictures"
            ) as response:
                user_infos = await response.json()
                avatars = {
                    u["basics"]["username"]: u["pictures"]["primary"]["url"]
                    for u in user_infos["them"]
                    if "pictures" in u
                }

        def owner_to_contact(o: ListMembersResponse.Result.Owner) -> Contact:
            name = o.fullName if o.fullName else o.username
            contact = Contact(
                id=o.uid,
                name=name,
                avatar=avatars.get(
                    o.username, f"https://api.dicebear.com/7.x/initials/svg?seed={name}"
                ),
            )
            return contact

        return list(owner_to_contact(o) for o in owners.values())

    async def conversations(self) -> list[Conversation]:
        me = WhoamiResponse(
            **json.loads(await self.run("whoami -j".split()))
        ).user.username
        data = await self.chat({"method": "list"})
        list_response = ListResponse(**data)
        conversations = list_response.result.conversations

        def get_username(channel: ListResponse.Result.Conversation.Channel) -> str:
            usernames = channel.name.split(",")

            if len(usernames) == 1:
                return usernames[0]

            usernames = [u for u in usernames if u != me]
            if len(usernames) != 1:
                raise ValueError(f"Expected only one user. Got: {usernames}")

            return usernames[0]

        individual_channels = [
            c.channel
            for c in conversations
            if c.channel.members_type
            != ListResponse.Result.Conversation.Channel.MemberType.team
        ]

        usernames = ",".join(map(get_username, individual_channels))
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://keybase.io/_/api/1.0/user/lookup.json",
                params={"usernames": usernames, "fields": "basics,profile,pictures"},
            ) as response:
                data = await response.json()
                users = {u["basics"]["username"]: u for u in data["them"] if u}

        def map_conversation(
            conversation: ListResponse.Result.Conversation,
        ) -> Conversation:
            if (
                conversation.channel.members_type
                == ListResponse.Result.Conversation.Channel.MemberType.team
            ):
                return Conversation(
                    id=conversation.id,
                    name=conversation.channel.name,
                    avatar=f"https://api.dicebear.com/7.x/initials/svg?seed={conversation.channel.name}",
                    last_active=datetime.fromtimestamp(
                        conversation.active_at_ms / 1000
                    ),
                )

            username = get_username(conversation.channel)
            user = users.get(username, {})
            full_name = user["profile"]["full_name"] if "profile" in user else username
            return Conversation(
                id=conversation.id,
                name=full_name,
                avatar=user["pictures"]["primary"]["url"]
                if "pictures" in user
                else f"https://api.dicebear.com/7.x/initials/svg?seed={full_name}",
                last_active=datetime.fromtimestamp(conversation.active_at_ms / 1000),
            )

        return sorted(
            map(map_conversation, conversations),
            key=lambda c: c.last_active,
            reverse=True,
        )

    async def messages(self, conversation_id: str = None):
        data = await self.chat(
            {
                "method": "read",
                "params": {
                    "options": {
                        "conversation_id": conversation_id,
                        "pagination": {"num": 100},
                    }
                },
            }
        )
        read_response = ReadResponse(**data)
        return sorted(
            (
                Message(
                    id=message.msg.id,
                    timestamp=datetime.fromtimestamp(message.msg.sent_at),
                    body=message.msg.content.text.body,
                    sender=message.msg.sender.uid,
                )
                for message in read_response.result.messages
                if message.msg.content.text
            ),
            key=lambda m: m.timestamp,
        )

    async def send_message(self, request: SendMessage):
        return await self.chat(
            {
                "method": "send",
                "params": {
                    "options": {
                        "conversation_id": request.conversation_id,
                        "message": {"body": request.body},
                        # "exploding_lifetime": "3h",
                    }
                },
            }
        )
