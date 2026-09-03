"""Programming plugin - because most users are broken developers."""
import re
from typing import Optional, List, Dict

from .base import Plugin, PluginResult


class ProgrammingPlugin(Plugin):
    """
    Handles code questions, debugging despair, and Git disasters.
    """

    name = "programming"
    triggers = ["coding", "python", "javascript", "git", "docker", "database", "frontend", "linux"]
    priority = 80

    def __init__(self):
        self._code_patterns = {
            r"\bbug\b": "Have you tried turning it off and on again? No? Then check your logic. Or don't. I'm not your debugger.",
            r"\berror\b": "Errors are just the compiler's way of saying 'I believe you meant to suffer.'",
            r"\bdebug\b": "Debugging is like being a detective in a crime movie where you are also the murderer.",
            r"\bgit\b": "Git is simple. You commit, you push, you pray. Sometimes you force push and ruin someone's week.",
            r"\bmerge conflict\b": "Merge conflicts are just Git's way of saying 'choose your fighter.'",
            r"\bdocker\b": "It works on my machine. Now put that machine in a container and never speak of it again.",
            r"\bpython\b": "Python: where indentation is law and semicolons are illegal immigrants.",
            r"\bjavascript\b": "JavaScript: where [] + {} gives you something, but don't ask what. Even it doesn't know.",
            r"\bsql\b": "SQL: the only language where you SELECT before you know what you want.",
            r"\bfrontend\b": "Frontend: where you spend 6 hours centering a div and call it a day.",
            r"\bbackend\b": "Backend: where the magic happens, and by magic I mean database timeouts.",
            r"\bapi\b": "APIs are just fancy URLs that judge your request format.",
        }

    async def handle(self, message: str, chat_id: int, 
                     context: List[Dict], **kwargs) -> Optional[PluginResult]:

        message_lower = message.lower()

        # Check for specific code patterns
        for pattern, response in self._code_patterns.items():
            if re.search(pattern, message_lower):
                return PluginResult(
                    response=response,
                    confidence=0.9,
                    intent="coding",
                    metadata={"pattern": pattern}
                )

        # Generic programming response
        if any(t in message_lower for t in ["code", "program", "dev", "developer", "function", "class", "variable"]):
            return PluginResult(
                response="Code is just organized suffering with syntax highlighting.",
                confidence=0.6,
                intent="coding"
            )

        return None
