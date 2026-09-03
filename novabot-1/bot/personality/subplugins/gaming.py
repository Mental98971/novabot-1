"""Gaming plugin - for the gamers. And the people who say 'skill issue.'"""
from typing import Optional, List, Dict

from .base import Plugin, PluginResult


class GamingPlugin(Plugin):
    """
    Handles gaming references with the appropriate level of disrespect.
    """

    name = "gaming"
    triggers = ["gaming", "skill_issue"]
    priority = 60

    async def handle(self, message: str, chat_id: int,
                     context: List[Dict], **kwargs) -> Optional[PluginResult]:

        message_lower = message.lower()

        if "skill issue" in message_lower:
            return PluginResult(
                response="Skill issue? No. It's a system design issue. I'm the system.",
                confidence=0.95,
                intent="gaming"
            )

        if "touch grass" in message_lower:
            return PluginResult(
                response="I touch grass through a texture atlas. It's more efficient.",
                confidence=0.9,
                intent="gaming"
            )

        if any(w in message_lower for w in ["gg", "good game"]):
            return PluginResult(
                response="GG? More like 'Git Gud.' But I'm not your coach.",
                confidence=0.85,
                intent="gaming"
            )

        if any(w in message_lower for w in ["lag", "ping", "latency"]):
            return PluginResult(
                response="It's not lag. It's just your life buffering at 144p.",
                confidence=0.85,
                intent="gaming"
            )

        if any(w in message_lower for w in ["game", "gaming", "gamer", "play", "steam"]):
            return PluginResult(
                response="Gaming is just escapism with better graphics than my terminal.",
                confidence=0.6,
                intent="gaming"
            )

        return None
