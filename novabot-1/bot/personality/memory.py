"""
Personality memory — conversation history, running gags, and joke
callback tracking for the banter/personality plugin.

Ported from nanora_bot's standalone `memory.py` (aiosqlite, its own
`nanora_memory.db` file) onto the shared SQLAlchemy database used by the
rest of NovaBot (see PersonalityMessage / PersonalityCallback / Chat in
bot/core/database.py), so there's one database file instead of two.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select

from bot.config import settings
from bot.core.database import Chat, PersonalityCallback, PersonalityMessage, async_session


@dataclass
class MessageContext:
    """A single message in conversation history."""
    role: str  # 'user' or 'bot'
    content: str
    timestamp: str
    intent: Optional[str] = None
    sentiment: Optional[str] = None


class MemoryManager:
    """Nanora remembers — not because she cares, but because callbacks land
    better when you know what you already mocked."""

    def __init__(self) -> None:
        self._local_cache: Dict[int, List[MessageContext]] = {}

    async def save_message(
        self, chat_id: int, role: str, content: str,
        intent: Optional[str] = None, sentiment: Optional[str] = None,
    ) -> None:
        async with async_session() as session:
            session.add(PersonalityMessage(chat_id=chat_id, role=role, content=content, intent=intent))
            await session.commit()

        bucket = self._local_cache.setdefault(chat_id, [])
        bucket.append(MessageContext(role, content, datetime.utcnow().isoformat(), intent, sentiment))
        if len(bucket) > settings.personality_max_context * 2:
            self._local_cache[chat_id] = bucket[-settings.personality_max_context:]

    async def get_context(self, chat_id: int, limit: int = 10) -> List[MessageContext]:
        """Retrieve recent conversation, for callbacks and continuity."""
        if chat_id in self._local_cache and len(self._local_cache[chat_id]) >= limit:
            return self._local_cache[chat_id][-limit:]

        async with async_session() as session:
            result = await session.execute(
                select(PersonalityMessage)
                .where(PersonalityMessage.chat_id == chat_id)
                .order_by(desc(PersonalityMessage.id))
                .limit(limit)
            )
            rows = list(reversed(result.scalars().all()))
            context = [
                MessageContext(
                    r.role, r.content,
                    r.created_at.isoformat() if r.created_at else "",
                    r.intent, None,
                )
                for r in rows
            ]
            self._local_cache[chat_id] = context
            return context

    @staticmethod
    async def _get_or_create_chat(session, chat_id: int) -> Chat:
        chat = await session.get(Chat, chat_id)
        if chat is None:
            chat = Chat(id=chat_id, type="private")
            session.add(chat)
            await session.flush()
        return chat

    async def get_user_profile(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """What little Nanora knows about this conversation. It's not much."""
        async with async_session() as session:
            chat = await session.get(Chat, chat_id)
            if chat is None:
                return None
            return {
                "chat_id": chat.id,
                "interaction_count": chat.personality_interactions or 0,
                "running_gags": chat.personality_running_gags or [],
            }

    async def update_profile(
        self, chat_id: int, username: Optional[str] = None, add_gag: Optional[str] = None,
    ) -> None:
        async with async_session() as session:
            chat = await self._get_or_create_chat(session, chat_id)
            chat.personality_interactions = (chat.personality_interactions or 0) + 1
            if add_gag:
                gags = list(chat.personality_running_gags or [])
                if add_gag not in gags:
                    gags.append(add_gag)
                    chat.personality_running_gags = gags[-10:]
            await session.commit()

    async def record_callback(self, chat_id: int, joke_id: str, context: str = "") -> None:
        """Remember that a joke was already used — don't repeat yourself."""
        async with async_session() as session:
            session.add(PersonalityCallback(chat_id=chat_id, joke_id=joke_id, context=context))
            await session.commit()

    async def was_callback_used(self, chat_id: int, joke_id: str, within_hours: int = 48) -> bool:
        cutoff = datetime.utcnow() - timedelta(hours=within_hours)
        async with async_session() as session:
            result = await session.execute(
                select(PersonalityCallback.id).where(
                    PersonalityCallback.chat_id == chat_id,
                    PersonalityCallback.joke_id == joke_id,
                    PersonalityCallback.created_at > cutoff,
                ).limit(1)
            )
            return result.first() is not None


memory = MemoryManager()
