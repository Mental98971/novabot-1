"""
Personality / banter plugin — ported from nanora_bot's bot.py.

Behavioural changes from the standalone bot:
  - /stats is renamed /mystats (NovaBot's own /stats means something
    else: chat-level moderation stats).
  - Personality no longer replies to every message in every chat by
    default. It's on by default in DMs (closest to the original's
    standalone behaviour) and OFF by default in groups — admins opt in
    per group with /personality on. Shipping a sarcastic auto-reply bot
    into every existing NovaBot moderation group without asking would
    be a surprising behaviour change, not a merge.
  - Fixed a real bug from the original: bot.py used `random.random()` in
    handle_message() without ever importing `random`, which would raise
    a NameError roughly 10% of the time a message matched an intent.
"""
from __future__ import annotations

import random
import time
from typing import Dict

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import settings
from bot.core.database import Chat, async_session
from bot.personality.jokes import jokes_db
from bot.personality.memory import memory
from bot.personality.personality import personality
from bot.personality.subplugins import AnimePlugin, GamingPlugin, GeneralPlugin, PluginManager, ProgrammingPlugin
from bot.personality.triggers import triggers

_cooldowns: Dict[int, float] = {}

_plugin_manager = PluginManager()
_plugin_manager.register(ProgrammingPlugin())
_plugin_manager.register(AnimePlugin())
_plugin_manager.register(GamingPlugin())
_plugin_manager.register(GeneralPlugin())


def _on_cooldown(user_id: int) -> bool:
    now = time.time()
    last = _cooldowns.get(user_id, 0)
    if now - last < settings.personality_cooldown_seconds:
        return True
    _cooldowns[user_id] = now
    return False


async def _is_enabled_for(chat_id: int, chat_type: str) -> bool:
    default = settings.personality_default_dm if chat_type == "private" else settings.personality_default_group
    async with async_session() as session:
        row = await session.get(Chat, chat_id)
        if row is not None and row.personality_enabled is not None:
            return row.personality_enabled
    return default


# ==================== COMMANDS ====================

async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await memory.save_message(chat_id, "user", "/joke", intent="joke_command")

    category = context.args[0].lower() if context.args else None
    joke = jokes_db.get_random(category)
    if joke:
        await memory.record_callback(chat_id, joke.id, "forced_joke")
        response = f"Fine. Here's your joke.\n\n{joke.text}\n\nHappy now?"
    else:
        response = "I don't have jokes about that. I'm not a circus."

    await update.message.reply_text(response)
    await memory.save_message(chat_id, "bot", response, intent="joke")


async def cmd_mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    profile = await memory.get_user_profile(chat_id)
    if profile:
        text = (
            f"Your stats? Fine.\n\n"
            f"Interactions: {profile['interaction_count']}\n"
            f"Running gags: {len(profile.get('running_gags', []))}\n\n"
            f"Satisfied? I didn't think so."
        )
    else:
        text = "No stats. You barely exist to me yet."
    await update.message.reply_text(text)


async def cmd_personality_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private":
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
            await update.message.reply_text("🚫 Admin only.")
            return

    arg = context.args[0].lower() if context.args else ""
    if arg not in ("on", "off"):
        await update.message.reply_text("Usage: /personality on  or  /personality off")
        return

    async with async_session() as session:
        row = await session.get(Chat, chat.id)
        if row is None:
            row = Chat(id=chat.id, type=chat.type)
            session.add(row)
        row.personality_enabled = arg == "on"
        await session.commit()

    await update.message.reply_text(f"🎭 Personality mode is now {'ON' if arg == 'on' else 'OFF'} here.")


# ==================== MESSAGE PIPELINE ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    1. Cooldown check
    2. Is personality mode active in this chat?
    3. Analyze triggers/intents
    4. Route to a sub-plugin or generate directly
    5. Rewrite with personality
    6. Send + save to memory
    """
    if not settings.enable_personality or not update.message or not update.message.text:
        return

    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text

    if _on_cooldown(user.id):
        return
    if not await _is_enabled_for(chat.id, chat.type):
        return

    await memory.update_profile(chat.id, username=user.username)

    trigger_matches = triggers.analyze(text)
    intents = [m.intent for m in trigger_matches]
    primary_intent = trigger_matches[0] if trigger_matches else None

    await memory.save_message(chat.id, "user", text, intent=primary_intent.intent if primary_intent else None)

    plugin_result = await _plugin_manager.route(text, chat.id, [], intents=intents)

    if plugin_result and plugin_result.response:
        response = await personality.rewrite(chat.id, plugin_result.response, intents, text)
    else:
        response = await personality.generate_direct(chat.id, intents, text)

    await update.message.reply_text(response)
    await memory.save_message(chat.id, "bot", response, intent=primary_intent.intent if primary_intent else "general")

    if primary_intent and random.random() < 0.1:
        await memory.update_profile(chat.id, add_gag=primary_intent.intent)


def register(app):
    if not settings.enable_personality:
        return

    app.add_handler(CommandHandler("joke", cmd_joke))
    app.add_handler(CommandHandler("mystats", cmd_mystats))
    app.add_handler(CommandHandler("personality", cmd_personality_toggle))

    # High group number: runs after moderation listeners (locks/filters,
    # groups 1-2), AFK (group 3), and font auto-style (group 5) — see the
    # comment in group_mgmt.py's register() for the full explanation of
    # why every catch-all text handler needs its own group.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message), group=10)
