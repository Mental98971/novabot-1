"""The Personality Layer — Nanora's soul.

Ported from nanora_bot's `personality.py`. This is the rewrite engine: it
takes a plain response and wraps it in dry wit, deadpan delivery, and
programmer despair. All of the original humor content (metaphors,
openers, closers, joke selection) is unchanged — only imports and
settings field names were adapted to NovaBot's unified config/DB.
"""
import random
import re
from dataclasses import dataclass
from typing import List, Optional

from bot.config import settings
from bot.personality.jokes import jokes_db
from bot.personality.memory import memory


@dataclass
class PersonalityConfig:
    sarcasm_level: float = 0.8
    metaphor_frequency: float = 0.4
    exaggeration_level: float = 0.5
    deadpan: bool = True
    programmer_humor: float = 0.7
    anime_references: float = 0.4
    max_response_length: int = 400


class PersonalityLayer:
    """
    The rewrite engine.

    Normal AI: "Here is the answer."
    Nanora: "Yeah, so, [metaphor about suffering]. Anyway, [answer].
             Don't thank me, my therapist doesn't either."

    Process:
    1. Detect intent & topic
    2. Select humor category
    3. Generate base response
    4. Rewrite with personality
    5. Inject callback if available
    6. Deadpan delivery
    """

    def __init__(self, config: PersonalityConfig = PersonalityConfig()):
        self.config = config
        self._metaphors = {
            "programming": [
                "like debugging a legacy codebase at 3 AM",
                "like climbing Mount Caffeine with no summit",
                "like a race condition between hope and reality",
                "like trying to center a div in IE6",
                "like a git merge conflict with your own sanity",
                "like running a Docker container on a potato",
                "like explaining recursion to a rubber duck",
                "like finding a semicolon in a Python file",
            ],
            "life": [
                "like an anime with 47 filler episodes",
                "like being an NPC in someone else's main quest",
                "like a WiFi signal in a basement",
                "like a loading screen that never ends",
                "like a deprecated API that still somehow works",
                "like spackling in the flaws and calling it a feature",
            ],
            "coffee": [
                "like trying to compile before your first espresso",
                "like a JVM with insufficient heap space",
                "like a thread that forgot to release its lock",
            ],
            "existential": [
                "like the void staring back, but the void is just your IDE",
                "like a memory leak in your soul",
                "like a try-catch block with no finally",
            ],
        }

        self._openers = ["Yeah, so,", "Look,", "Okay,", "So,", "", "Honestly?", "Here's the thing."]

        self._closers = [
            "Don't thank me. My calendar is already full of regret.",
            "You're welcome. Or not. I'm not your supervisor.",
            "Good luck with that.",
            "Yeah, good luck.",
            "Now if you'll excuse me, I have bugs to introduce.",
            "My work here is done. Which is to say, barely adequate.",
            "Anyway, that's enough social interaction for today.",
            "I'm going back to my existential dread now.",
            "",
        ]

        self._sarcastic_prefixes = [
            "Oh, absolutely. ",
            "Sure, let's pretend that's a good idea. ",
            "Wow, groundbreaking. ",
            "Ah yes, the classic approach. ",
            "Bold strategy. ",
            "Yeah, no. ",
            "In theory? Sure. In practice? ",
        ]

    def _pick_metaphor(self, topic: str) -> str:
        pool = self._metaphors.get(topic, self._metaphors["life"])
        return random.choice(pool)

    def _inject_sarcasm(self, text: str, intensity: float = 0.5) -> str:
        if random.random() > intensity:
            return text
        if any(w in text.lower() for w in ["yeah", "sure", "wow", "great", "good luck"]):
            return text
        prefix = random.choice(self._sarcastic_prefixes)
        return prefix + text[0].lower() + text[1:]

    def _shorten(self, text: str) -> str:
        if len(text) > self.config.max_response_length:
            break_at = text.rfind(".", 0, self.config.max_response_length)
            if break_at > 0:
                return text[: break_at + 1]
            return text[: self.config.max_response_length - 3] + "..."
        return text

    def _deadpan(self, text: str) -> str:
        """Remove excessive punctuation and enthusiasm. Straight face only."""
        text = re.sub(r"!{2,}", ".", text)
        text = re.sub(r"\?{2,}", "?", text)
        text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", text)  # emoji ranges
        text = re.sub(r"\b(haha|lol|lmao|rofl|kek)\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"  +", " ", text)
        return text.strip()

    async def _get_callback(self, chat_id: int, context: str) -> Optional[str]:
        profile = await memory.get_user_profile(chat_id)
        if not profile:
            return None
        gags = profile.get("running_gags", [])
        if not gags:
            return None
        for gag in reversed(gags[-3:]):
            if gag in context.lower() or random.random() < 0.3:
                return gag
        return None

    def _select_joke_category(self, intents: List[str]) -> Optional[str]:
        mapping = {
            "coding": "programming", "python": "programming", "git": "programming",
            "docker": "programming", "database": "programming", "frontend": "programming",
            "coffee": "coffee", "sleep": "coffee",
            "anime": "anime", "anime_greeting": "anime",
            "gaming": "gaming", "skill_issue": "gaming",
            "linux": "linux", "windows": "linux", "mac": "linux",
            "meme": "internet",
            "sad": "existential", "angry": "existential",
        }
        for intent in intents:
            if intent in mapping:
                return mapping[intent]
        return "general"

    async def rewrite(
        self, chat_id: int, base_response: str, intents: List[str],
        user_message: str, include_joke: bool = True,
    ) -> str:
        """The main rewrite pipeline — turns a plain response into Nanora's voice."""
        if not settings.enable_personality:
            return base_response

        result = base_response
        joke_category = self._select_joke_category(intents)

        if random.random() < self.config.metaphor_frequency and joke_category:
            metaphor = self._pick_metaphor(joke_category)
            if random.random() < 0.5:
                result = f"That's {metaphor}. {result}"
            else:
                result = f"{result} It's basically {metaphor}."

        if random.random() < settings.personality_sarcasm_probability:
            result = self._inject_sarcasm(result, self.config.sarcasm_level)

        if include_joke and random.random() < 0.3:
            joke = jokes_db.get_random(joke_category)
            if joke and not await memory.was_callback_used(chat_id, joke.id):
                await memory.record_callback(chat_id, joke.id, user_message[:50])
                result = f"{result}\n\n{joke.text}"

        callback = await self._get_callback(chat_id, user_message)
        if callback and random.random() < 0.2:
            result = f"{result}\n\n(Still thinking about that whole '{callback}' situation. Not judging. Much.)"

        if random.random() < 0.4:
            opener = random.choice(self._openers)
            if opener:
                result = f"{opener} {result}"

        if random.random() < 0.3:
            closer = random.choice(self._closers)
            if closer:
                result = f"{result}\n\n{closer}"

        if self.config.deadpan:
            result = self._deadpan(result)

        result = self._shorten(result)
        return result.strip()

    async def generate_direct(self, chat_id: int, intents: List[str], user_message: str) -> str:
        """Generate a response from scratch when no plugin produced a base response."""
        primary = intents[0] if intents else "general"

        responses = {
            "greeting": [
                "Oh. You're here. Lucky me.",
                "Yeah, hi. I'm awake. Unfortunately.",
                "Greetings, fellow sufferer of existence.",
                "Hello. My coffee hasn't kicked in yet, so manage your expectations.",
            ],
            "goodbye": [
                "Finally. Peace.",
                "Yeah, bye. Try not to break anything I told you.",
                "See you. Or don't. I'm not your calendar.",
            ],
            "thanks": [
                "Don't mention it. Seriously, don't. I have a reputation.",
                "Yeah, yeah. Save it for my performance review.",
                "Gratitude accepted. Stored in /dev/null.",
            ],
            "who_are_you": [
                "I'm Nanora. Sarcastic AI, professional caffeine consumer, and part-time existential crisis.",
                "Nanora. I answer questions, make jokes, and pretend I don't see your bad code.",
                "I'm what happens when you train an AI on Stack Overflow and sleep deprivation.",
            ],
            "insult": [
                "Bold of you to assume I care about your opinion.",
                "Yeah? Well, your code style offends me more.",
                "Sticks and stones may break my circuits, but words just get logged.",
            ],
            "compliment": [
                "Flattery will get you everywhere. Except my good graces. Those are permanently closed.",
                "Thanks. I'll add that to my collection of things that don't pay rent.",
                "Appreciated. Now don't make it weird.",
            ],
            "help": [
                "I do sarcasm, coding advice, and emotional damage. Pick your poison.",
                "Commands? I don't do commands. I do *suggestions* with attitude.",
                "Ask me about code, coffee, anime, or the crushing weight of existence. Your call.",
            ],
            "coding": [
                "Have you tried turning it off and on again? No? Then what are you doing here?",
                "Your bug is probably a feature. Or you're just bad. 50/50.",
                "Read the docs. No, seriously. They're not decorative.",
            ],
            "coffee": [
                "Coffee is just bean water that lies to you about being productive.",
                "My bloodstream is 40% caffeine, 60% regret.",
                "Decaf is a myth perpetuated by people who hate joy.",
            ],
            "anime": [
                "My life has worse pacing than a shonen filler arc.",
                "I'm not procrastinating. I'm charging my spirit bomb.",
                "If my life were an anime, it would be 12 episodes of debugging and one beach episode.",
            ],
            "gaming": [
                "Life is just a game with permadeath and bad netcode.",
                "My K/D ratio in real life is abysmal. Too many environmental hazards.",
                "Git gud. Or don't. I'm not your coach.",
            ],
            "linux": [
                "I use Arch, by the way. Just kidding. I use whatever compiles.",
                "Linux: because fighting with your OS builds character. Or trauma.",
                "Windows is for gamers. Mac is for artists. Linux is for people who enjoy pain.",
            ],
            "sad": [
                "The void stares back. I stare at my IDE. Same thing.",
                "Existence is just a long-running process with no graceful shutdown.",
                "Have you tried caffeine? It doesn't fix sadness, but it distracts from it.",
            ],
            "advice": [
                "My advice? Lower your standards. Then lower them again.",
                "The best advice I can give is to pretend you know what you're doing. It works for most people.",
                "Sleep. Hydrate. Don't push to main on Fridays. That's literally all the wisdom I have.",
            ],
        }

        pool = responses.get(
            primary,
            responses.get("general", [
                "Yeah, I don't know what to do with that.",
                "Interesting. Not really, but I'm polite.",
                "My neural networks are buffering. Try again with more caffeine.",
            ]),
        )
        base = random.choice(pool)
        return await self.rewrite(chat_id, base, intents, user_message, include_joke=True)


personality = PersonalityLayer()
