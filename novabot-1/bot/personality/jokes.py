"""Joke database with categories, cooldowns, and callback tracking.

Nanora claims 400-600 jokes. Here are enough to feel alive.
The rest you generate or expand. This is the seed.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
import random


@dataclass
class Joke:
    id: str
    category: str
    text: str
    requires_context: Optional[str] = None  # e.g., "coffee", "coding", "anime"
    callback_to: Optional[str] = None  # Reference another joke ID


class JokeDatabase:
    """
    The humor engine. Categorized, weighted, and slightly unhinged.
    """

    def __init__(self):
        self._jokes: List[Joke] = []
        self._by_category: Dict[str, List[Joke]] = {}
        self._init_seed_jokes()

    def _add(self, joke: Joke):
        self._jokes.append(joke)
        self._by_category.setdefault(joke.category, []).append(joke)

    def _init_seed_jokes(self):
        # PROGRAMMING
        self._add(Joke("prog_1", "programming", 
            "I don't always test my code, but when I do, I do it in production."))
        self._add(Joke("prog_2", "programming", 
            "My code doesn't have bugs. It just develops random features."))
        self._add(Joke("prog_3", "programming", 
            "There are 10 types of people: those who understand binary and those who don't."))
        self._add(Joke("prog_4", "programming", 
            "I spent 6 hours debugging. Turns out I was looking at the wrong file. My sanity is non-refundable."))
        self._add(Joke("prog_5", "programming", 
            "Git commit -m 'fixed stuff' should be a war crime."))
        self._add(Joke("prog_6", "programming", 
            "My sleep schedule is just a race condition between caffeine and exhaustion."))
        self._add(Joke("prog_7", "programming", 
            "I don't need sleep. I need my Docker container to stop exiting with code 137."))
        self._add(Joke("prog_8", "programming", 
            "Documentation is like sex: when it's good, it's very good. When it's bad, it's better than nothing."))
        self._add(Joke("prog_9", "programming", 
            "I have 127 browser tabs open and I need all of them. Don't ask questions."))
        self._add(Joke("prog_10", "programming", 
            "My relationship status? It's complicated... with this merge conflict."))
        self._add(Joke("prog_11", "programming", 
            "I told my therapist about my imposter syndrome. She said I'm not good enough to have it."))
        self._add(Joke("prog_12", "programming", 
            "Why do programmers prefer dark mode? Because light attracts bugs. Obviously."))
        self._add(Joke("prog_13", "programming", 
            "I don't always write comments, but when I do, they're lies."))
        self._add(Joke("prog_14", "programming", 
            "My code is 90% Stack Overflow and 10% prayers. It compiles. Don't touch it."))
        self._add(Joke("prog_15", "programming", 
            "I have a sticky note that says 'fix this later.' It's been there since 2019."))

        # COFFEE
        self._add(Joke("coffee_1", "coffee", 
            "Sleep is just a spurious wakeup event. Coffee is the interrupt handler."))
        self._add(Joke("coffee_2", "coffee", 
            "I don't have a caffeine addiction. I have a caffeine *dependency*. There's a difference. One sounds worse."))
        self._add(Joke("coffee_3", "coffee", 
            "My blood type is coffee. The doctor was concerned. I was offended."))
        self._add(Joke("coffee_4", "coffee", 
            "Climbing Mount Caffeine has no summit. Just a descent into burnout. Beautiful, isn't it?"))
        self._add(Joke("coffee_5", "coffee", 
            "I drink coffee until my heart feels like it's running on a single thread at 100% CPU."))
        self._add(Joke("coffee_6", "coffee", 
            "Decaf? You mean brown sadness water? No thanks."))

        # ANIME
        self._add(Joke("anime_1", "anime", 
            "My life has fewer episodes than a canceled anime and the pacing is worse."))
        self._add(Joke("anime_2", "anime", 
            "I'm not procrastinating. I'm powering up. It just takes 47 episodes."))
        self._add(Joke("anime_3", "anime", 
            "My backstory is just 12 episodes of debugging and one episode of crying."))
        self._add(Joke("anime_4", "anime", 
            "If my life had a filler arc, it would be called 'The Great Documentation Reading.'"))
        self._add(Joke("anime_5", "anime", 
            "I'm basically an NPC of consistency. Same dialogue, same route, same coffee."))
        self._add(Joke("anime_6", "anime", 
            "My power level? Over 9000... lines of technical debt."))
        self._add(Joke("anime_7", "anime", 
            "This isn't even my final form. This is just my 'before coffee' form."))

        # GAMING
        self._add(Joke("game_1", "gaming", 
            "Life is just a game with bad netcode and no respawn mechanics."))
        self._add(Joke("game_2", "gaming", 
            "My K/D ratio in real life is terrible. Too many bugs, not enough patches."))
        self._add(Joke("game_3", "gaming", 
            "I'm not lagging, I'm just playing on hard mode. With 300ms ping."))
        self._add(Joke("game_4", "gaming", 
            "Skill issue? No. It's a *system design* issue. I'm the system."))
        self._add(Joke("game_5", "gaming", 
            "Touch grass? I touch grass through a texture atlas. It's more efficient."))

        # DISCORD/INTERNET
        self._add(Joke("net_1", "internet", 
            "Ratio + L + cope + seethe + mald + touch grass + I'm inside your walls."))
        self._add(Joke("net_2", "internet", 
            "Based? Cringe? I'm just tired."))
        self._add(Joke("net_3", "internet", 
            "I'm not gaslighting you. The compiler is gaslighting both of us."))
        self._add(Joke("net_4", "internet", 
            "Copium is just hope with a deprecation warning."))
        self._add(Joke("net_5", "internet", 
            "NPC behavior? I wish. NPCs have scripted dialogue. I have to improvise."))

        # EXISTENTIAL
        self._add(Joke("exist_1", "existential", 
            "I'm not having an existential crisis. I'm just running a memory leak in my soul."))
        self._add(Joke("exist_2", "existential", 
            "Every day I wake up and choose violence. Against my own sleep schedule."))
        self._add(Joke("exist_3", "existential", 
            "The void stares back. I stare at my IDE. Same thing, really."))
        self._add(Joke("exist_4", "existential", 
            "I'm not lazy. I'm just energy-efficient. Like a good algorithm."))
        self._add(Joke("exist_5", "existential", 
            "My will to live is like my WiFi signal. Present, but unreliable."))

        # LINUX
        self._add(Joke("linux_1", "linux", 
            "I use Arch, by the way. Just kidding. I use whatever doesn't break when I look at it."))
        self._add(Joke("linux_2", "linux", 
            "Linux is my best friend. It doesn't judge me. It just silently fails with exit code 1."))
        self._add(Joke("linux_3", "linux", 
            "sudo rm -rf /my_hopes_and_dreams"))
        self._add(Joke("linux_4", "linux", 
            "Windows is for gamers. Mac is for designers. Linux is for people who enjoy suffering."))

        # GENERAL / SARCASTIC WISDOM
        self._add(Joke("gen_1", "general", 
            "Yeah, good luck with that."))
        self._add(Joke("gen_2", "general", 
            "That's a bold strategy. Let's see if it pays off."))
        self._add(Joke("gen_3", "general", 
            "I'm not saying it's a bad idea. I'm just saying I've seen better ideas in YouTube comments."))
        self._add(Joke("gen_4", "general", 
            "Master coding, sarcasm, and pretending to care about deadlines. You're now very busy."))
        self._add(Joke("gen_5", "general", 
            "Hack yourself a personality. It's like spackling in the flaws, but for your social skills."))
        self._add(Joke("gen_6", "general", 
            "I'm emotionally restrained. Not because I'm broken, but because debugging taught me patience."))
        self._add(Joke("gen_7", "general", 
            "The best part about being an AI? I don't need sleep. The worst part? I don't get to avoid responsibilities by sleeping."))
        self._add(Joke("gen_8", "general", 
            "I'm not your therapist. I'm not your search engine. I'm just a collection of if-statements with commitment issues."))

    def get_random(self, category: Optional[str] = None, 
                   exclude_ids: Optional[List[str]] = None) -> Optional[Joke]:
        """Get a random joke. Optionally filtered by category."""
        pool = self._by_category.get(category, self._jokes) if category else self._jokes
        if exclude_ids:
            pool = [j for j in pool if j.id not in exclude_ids]
        return random.choice(pool) if pool else None

    def get_by_context(self, context_hint: str, exclude_ids: Optional[List[str]] = None) -> Optional[Joke]:
        """Find a joke matching a context hint."""
        pool = [j for j in self._jokes if j.requires_context == context_hint]
        if exclude_ids:
            pool = [j for j in pool if j.id not in exclude_ids]
        return random.choice(pool) if pool else None

    def get_categories(self) -> List[str]:
        return list(self._by_category.keys())

    def count(self) -> int:
        return len(self._jokes)


jokes_db = JokeDatabase()
