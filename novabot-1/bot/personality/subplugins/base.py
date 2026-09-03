"""Base plugin architecture.

If you want to add more chaos, inherit from Plugin.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class PluginResult:
    """What a plugin returns after processing."""
    response: Optional[str] = None
    confidence: float = 0.0
    intent: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class Plugin(ABC):
    """Base class for all plugins."""

    name: str = "base"
    triggers: List[str] = []  # Intent strings this plugin handles
    priority: int = 50  # Higher = checked first

    @abstractmethod
    async def handle(self, message: str, chat_id: int, 
                     context: List[Dict], **kwargs) -> Optional[PluginResult]:
        """Process a message. Return None if this plugin doesn't handle it."""
        pass

    async def on_load(self):
        """Called when plugin is loaded. Override if needed."""
        pass


class PluginManager:
    """Routes messages to the right plugin. Or the wrong one. It's chaotic."""

    def __init__(self):
        self._plugins: List[Plugin] = []

    def register(self, plugin: Plugin):
        self._plugins.append(plugin)
        self._plugins.sort(key=lambda p: p.priority, reverse=True)

    async def route(self, message: str, chat_id: int, 
                    context: List[Dict], intents: List[str], **kwargs) -> Optional[PluginResult]:
        """Find the best plugin for this message."""
        for plugin in self._plugins:
            # Check if any intent matches plugin triggers
            if any(intent in plugin.triggers for intent in intents):
                result = await plugin.handle(message, chat_id, context, **kwargs)
                if result and result.confidence > 0.5:
                    return result

        # Fallback: try all plugins
        for plugin in self._plugins:
            if not any(intent in plugin.triggers for intent in intents):
                result = await plugin.handle(message, chat_id, context, **kwargs)
                if result and result.confidence > 0.7:
                    return result

        return None
