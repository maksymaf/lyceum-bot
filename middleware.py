from typing import Any, Awaitable, Callable, Dict
from aiogram.fsm.storage.redis import RedisStorage
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from config import FLOOD_TIMING

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, storage: RedisStorage):
        self.storage = storage

    async def __call__(self, handler : Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],  event: Message, data: Dict) -> Any:
        user = f'user{event.from_user.id}'
        check_user = await self.storage.redis.get(name=user)

        if check_user:
            if int(check_user.decode()) == 1:
                await self.storage.redis.set(name=user, value=0, ex=10)
                return await event.answer('Не флуди. Почекай 10 секунд')
            return 
        await self.storage.redis.set(name=user, value=1, ex=FLOOD_TIMING)

        return await handler(event, data);