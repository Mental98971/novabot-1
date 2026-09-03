"""NLP trigger system - regex + keyword detection.

Nanora doesn't do fancy transformers. She does regex and spite.
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TriggerMatch:
    intent: str
    confidence: float
    matched_text: str
    category: str


class TriggerEngine:
    """
    Pattern matching with the elegance of a sledgehammer.
    Fast. Brutal. Effective.
    """

    def __init__(self):
        self.patterns: List[Tuple[str, str, re.Pattern, float]] = []
        self._init_patterns()

    def _add(self, intent: str, category: str, pattern: str, weight: float = 1.0):
        self.patterns.append((intent, category, re.compile(pattern, re.IGNORECASE), weight))

    def _init_patterns(self):
        # GREETINGS
        self._add("greeting", "social", r"\b(hi|hello|hey|yo|sup|hola|greetings)\b", 0.9)
        self._add("goodbye", "social", r"\b(bye|goodbye|see ya|cya|later|night)\b", 0.9)
        self._add("thanks", "social", r"\b(thanks|thank you|ty|appreciate)\b", 0.8)

        # PROGRAMMING
        self._add("coding", "programming", r"\b(code|coding|program|programming|dev|developer|bug|debug|compile|error|exception)\b", 0.85)
        self._add("python", "programming", r"\bpython\b", 0.95)
        self._add("javascript", "programming", r"\b(javascript|js|node\.js|nodejs)\b", 0.95)
        self._add("git", "programming", r"\b(git|github|commit|merge|branch|pull request|pr)\b", 0.9)
        self._add("docker", "programming", r"\b(docker|container|kubernetes|k8s)\b", 0.9)
        self._add("database", "programming", r"\b(database|db|sql|sqlite|postgres|mongodb)\b", 0.85)
        self._add("frontend", "programming", r"\b(frontend|react|vue|angular|html|css|ui|ux)\b", 0.85)

        # COFFEE
        self._add("coffee", "lifestyle", r"\b(coffee|espresso|latte|caffeine|brew|starbucks)\b", 0.9)
        self._add("sleep", "lifestyle", r"\b(sleep|tired|exhausted|insomnia|nap|bed)\b", 0.8)

        # ANIME
        self._add("anime", "anime", r"\b(anime|manga|waifu|weeb|otaku|naruto|dragon ball|one piece|attack on titan)\b", 0.9)
        self._add("anime_greeting", "anime", r"\b(ohayo|konnichiwa|konbanwa|sayonara|arigato|senpai|kouhai)\b", 0.95)

        # GAMING
        self._add("gaming", "gaming", r"\b(game|gaming|gamer|play|steam|xbox|playstation|nintendo|minecraft|valorant)\b", 0.85)
        self._add("skill_issue", "gaming", r"\b(skill issue|git gud|noob|ez|gg|wp)\b", 0.9)

        # LINUX
        self._add("linux", "tech", r"\b(linux|ubuntu|debian|arch|fedora|vim|emacs|terminal|bash|shell)\b", 0.9)
        self._add("windows", "tech", r"\b(windows|microsoft|bill gates)\b", 0.85)
        self._add("mac", "tech", r"\b(mac|macbook|apple|osx|macos)\b", 0.85)

        # INTERNET/MEMES
        self._add("meme", "internet", r"\b(ratio|based|cringe|copium|touch grass|npc|mald|seethe|cope)\b", 0.9)
        self._add("meme", "internet", r"\b(bruh|lol|lmao|kek|poggers|monka)\b", 0.7)

        # EMOTIONAL
        self._add("sad", "emotional", r"\b(sad|depressed|lonely|cry|tears|hurt|pain|suffering)\b", 0.8)
        self._add("happy", "emotional", r"\b(happy|joy|excited|awesome|amazing|great|wonderful)\b", 0.7)
        self._add("angry", "emotional", r"\b(angry|mad|furious|hate|rage|annoyed|frustrated)\b", 0.8)

        # META / ABOUT NANORA
        self._add("who_are_you", "meta", r"\b(who are you|what are you|your name|about you|introduce)\b", 0.9)
        self._add("help", "meta", r"\b(help|commands|what can you do|features)\b", 0.8)
        self._add("insult", "meta", r"\b(stupid|dumb|idiot|useless|bad bot|shut up)\b", 0.85)
        self._add("compliment", "meta", r"\b(smart|good bot|amazing|best|love you|cool)\b", 0.8)

        # QUESTIONS
        self._add("how_to", "question", r"\b(how (to|do|can|should)|what (is|are)|why (is|does)|when (is|will))\b", 0.75)
        self._add("advice", "question", r"\b(advice|tip|suggest|recommend|should i)\b", 0.8)

    def analyze(self, text: str) -> List[TriggerMatch]:
        """Analyze text and return matched intents sorted by confidence."""
        matches = []
        for intent, category, pattern, weight in self.patterns:
            match = pattern.search(text)
            if match:
                confidence = min(1.0, weight * (len(match.group()) / max(len(text), 1)) * 3 + 0.3)
                matches.append(TriggerMatch(intent, confidence, match.group(), category))

        # Deduplicate by intent, keep highest confidence
        seen = {}
        for m in matches:
            if m.intent not in seen or seen[m.intent].confidence < m.confidence:
                seen[m.intent] = m

        return sorted(seen.values(), key=lambda x: x.confidence, reverse=True)

    def primary_intent(self, text: str) -> Optional[TriggerMatch]:
        """Get the top intent. Or None, if you're being cryptic."""
        matches = self.analyze(text)
        return matches[0] if matches else None


triggers = TriggerEngine()
