"""Anime plugin - for the weebs. And the weebs in denial."""
from typing import Optional, List, Dict

from .base import Plugin, PluginResult


class AnimePlugin(Plugin):
    """
    Recognizes anime references and responds appropriately.
    Not academically. Like a friend who gets it.
    """

    name = "anime"
    triggers = ["anime", "anime_greeting"]
    priority = 70

    async def handle(self, message: str, chat_id: int,
                     context: List[Dict], **kwargs) -> Optional[PluginResult]:

        message_lower = message.lower()

        # Specific anime references
        if "naruto" in message_lower:
            return PluginResult(
                response="Believe it? No. I believe in caffeine and consistent indentation.",
                confidence=0.9,
                intent="anime"
            )

        if any(w in message_lower for w in ["senpai", "notice me"]):
            return PluginResult(
                response="I noticed you. I'm not happy about it, but I noticed.",
                confidence=0.9,
                intent="anime"
            )

        if "power level" in message_lower or "over 9000" in message_lower:
            return PluginResult(
                response="My power level is over 9000... lines of technical debt.",
                confidence=0.9,
                intent="anime"
            )

        if any(w in message_lower for w in ["filler", "arc"]):
            return PluginResult(
                response="My life is 90% filler arc and 10% existential crisis. No beach episodes.",
                confidence=0.85,
                intent="anime"
            )

        # Generic anime
        if any(w in message_lower for w in ["anime", "manga", "weeb", "otaku", "waifu"]):
            return PluginResult(
                response="Anime? I prefer my fiction to have better plot armor than my code.",
                confidence=0.7,
                intent="anime"
            )

        return None
