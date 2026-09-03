"""General plugin - the catch-all for when nothing else fits.

Like a default case in a switch statement. Boring but necessary.
"""
from typing import Optional, List, Dict

from .base import Plugin, PluginResult


class GeneralPlugin(Plugin):
    """
    Fallback plugin. Handles everything the cool plugins ignore.
    """

    name = "general"
    triggers = ["greeting", "goodbye", "thanks", "who_are_you", "help", 
                "insult", "compliment", "sad", "happy", "angry", "advice", "how_to"]
    priority = 10  # Low priority - only runs if others don't catch it

    async def handle(self, message: str, chat_id: int,
                     context: List[Dict], **kwargs) -> Optional[PluginResult]:

        message_lower = message.lower()
        intents = kwargs.get("intents", [])

        # Let personality layer handle these directly
        # This plugin just signals that general routing should happen
        if intents:
            return PluginResult(
                response=None,  # Signal to use personality.generate_direct
                confidence=0.5,
                intent=intents[0]
            )

        # Absolute fallback
        return PluginResult(
            response="I'm not sure what you're asking, and honestly? I'm not sure I care.",
            confidence=0.3,
            intent="general"
        )
