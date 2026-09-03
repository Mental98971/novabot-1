"""Internal intent-routing plugins for the personality layer.

Not to be confused with bot/plugins/ (NovaBot's top-level Telegram
command plugins) — these are nanora_bot's original, smaller plugin
system that routes a message to a topical responder (programming, anime,
gaming, or a general fallback) before the personality layer rewrites it.
"""
from .base import Plugin, PluginManager, PluginResult
from .programming import ProgrammingPlugin
from .anime import AnimePlugin
from .gaming import GamingPlugin
from .general import GeneralPlugin

__all__ = [
    "Plugin", "PluginManager", "PluginResult",
    "ProgrammingPlugin", "AnimePlugin", "GamingPlugin", "GeneralPlugin",
]
