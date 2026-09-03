"""
Character Collector — ambient "guess the name" catching game.

Sourced from four sibling projects this round (three single-file
anime_collector_bot variants plus the more production-shaped
anime_catcher_bot), cross-referenced against WAIFU-HUSBANDO-CATCHER
from an earlier round. All four independently implement the same
core loop (a character spawns based on chat activity, first person to
correctly /grab its name catches it), so rather than pick one to port
verbatim, this rebuilds that loop against NovaBot's own architecture
and reuses what already exists instead of duplicating it:

  - Catch rewards pay into the existing coin economy
    (bot/services/economy_service.py) instead of a second currency.
  - /topcatchers is a new, distinctly-named ranking — /leaderboard
    already means XP ranking (see plugins/economy.py).
  - No separate /daily, /broadcast, /stats, /botban: the source
    projects' versions of these overlap with existing NovaBot commands
    (/daily, /broadcast, /stats, /gban+/block) that already do the job.
  - Trade proposals use inline accept/decline (bot/plugins/games.py's
    "game:" callback pattern, mirrored here as "collector:" — see that
    file's module docstring for why every inline keyboard in this
    project needs its own callback_data prefix).

Characters are shared bot-wide (upload once, catchable in every chat),
curated by a small "collector moderator" role that's intentionally
separate from being an admin of any one chat — matches how the source
projects scope it, and makes sense given the content is shared across
every chat NovaBot is in, not owned by any single one.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import settings
from bot.core.database import (
    Character,
    Chat,
    CollectorModerator,
    Giveaway,
    User,
    UserCharacter,
    async_session,
)
from bot.core.decorators import admin_only, group_only
from bot.services.economy_service import add_coins
from bot.utils.helpers import escape_html, paginate, resolve_target_user

RARITY_EMOJIS = {
    "common": "⚪", "uncommon": "🟢", "rare": "🔵",
    "epic": "🟣", "legendary": "🟡", "divine": "🔴",
}
RARITY_ORDER = list(RARITY_EMOJIS)

# Ephemeral, in-memory — same trade-off as games.py's trivia/tic-tac-toe
# state: a restart simply ends whatever was in progress.
_message_counters: Dict[int, int] = {}          # chat_id -> messages since last spawn
_current_spawns: Dict[int, dict] = {}            # chat_id -> {"id", "name", "anime", "rarity", "image_url"}
_pending_trades: Dict[tuple, dict] = {}          # (proposer_id, target_id) -> {char ids, expires}


async def _is_collector_mod(user_id: int) -> bool:
    if settings.is_admin_id(user_id):
        return True
    async with async_session() as session:
        return await session.get(CollectorModerator, user_id) is not None


async def _pick_character(session) -> Optional[Character]:
    count = (await session.execute(select(func.count()).select_from(Character))).scalar() or 0
    if not count:
        return None
    offset = random.randint(0, count - 1)
    result = await session.execute(select(Character).offset(offset).limit(1))
    return result.scalar_one_or_none()


def _rarity_emoji(rarity: str) -> str:
    return RARITY_EMOJIS.get((rarity or "common").lower(), "⚪")


async def _do_spawn(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        char = await _pick_character(session)
    if not char:
        return

    _current_spawns[chat_id] = {
        "id": char.id, "name": char.name, "anime": char.anime,
        "rarity": char.rarity, "image_url": char.image_url,
    }
    caption = (
        f"🎉 A wild {_rarity_emoji(char.rarity)} <b>{char.rarity.title()}</b> character appeared!\n\n"
        f"Series: {escape_html(char.anime or 'Unknown')}\n"
        f"Type <code>/grab &lt;name&gt;</code> to catch it!"
    )
    try:
        if char.image_url:
            await context.bot.send_photo(chat_id, photo=char.image_url, caption=caption, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id, caption, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(chat_id, caption, parse_mode="HTML")


async def spawn_listener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ambient spawns based on chat activity — own handler group, see
    group_mgmt.py's register() for why every catch-all text handler
    needs one."""
    if not settings.enable_collector or not update.effective_chat or update.effective_chat.type == "private":
        return
    chat_id = update.effective_chat.id

    async with async_session() as session:
        chat_row = await session.get(Chat, chat_id)
        rate = (chat_row.collector_spawn_rate if chat_row else None) or settings.collector_default_spawn_rate

    _message_counters[chat_id] = _message_counters.get(chat_id, 0) + 1
    if _message_counters[chat_id] >= rate and chat_id not in _current_spawns:
        _message_counters[chat_id] = 0
        await _do_spawn(chat_id, context)


@group_only
async def spawn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_collector_mod(update.effective_user.id):
        await update.message.reply_text("🚫 Collector moderators only. See /mods")
        return
    await _do_spawn(update.effective_chat.id, context)


@group_only
async def grab_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    spawn = _current_spawns.get(chat_id)
    if not spawn:
        await update.message.reply_text("❌ Nothing to grab right now — wait for a spawn.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /grab <character name>")
        return

    guess = " ".join(context.args).strip().lower()
    if guess != spawn["name"].lower():
        await update.message.reply_text("❌ Wrong name!")
        return

    # No `await` between the check above and this pop, so under asyncio's
    # cooperative scheduling this is effectively atomic — a second
    # near-simultaneous correct guess finds the spawn already gone.
    del _current_spawns[chat_id]

    user = update.effective_user
    async with async_session() as session:
        session.add(UserCharacter(user_id=user.id, character_id=spawn["id"]))
        await session.commit()

    new_balance = await add_coins(chat_id, user.id, settings.collector_catch_reward_coins)
    await update.message.reply_text(
        f"🎉 <b>{escape_html(user.first_name)}</b> caught <b>{escape_html(spawn['name'])}</b> "
        f"({_rarity_emoji(spawn['rarity'])} {spawn['rarity'].title()})! "
        f"+{settings.collector_catch_reward_coins} 🪙 (balance: {new_balance:,})",
        parse_mode="HTML",
    )


async def collection_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
    target_id, target_name = update.effective_user.id, update.effective_user.first_name
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name

    async with async_session() as session:
        result = await session.execute(
            select(UserCharacter, Character)
            .join(Character, Character.id == UserCharacter.character_id)
            .where(UserCharacter.user_id == target_id)
            .order_by(UserCharacter.id.desc())
        )
        rows = result.all()

    if not rows:
        await update.message.reply_text(f"📭 {escape_html(target_name)} hasn't caught anyone yet.", parse_mode="HTML")
        return

    lines_all = [
        f"{'⭐' if uc.is_favorite else _rarity_emoji(c.rarity)} <b>{escape_html(c.name)}</b> "
        f"({escape_html(c.anime or '?')}) — <code>{c.id}</code>"
        for uc, c in rows
    ]
    page_items, total, pages = paginate(lines_all, page, per_page=15)
    await update.message.reply_text(
        f"📚 <b>{escape_html(target_name)}'s Collection</b> ({total} total) — page {page}/{pages}\n\n"
        + "\n".join(page_items) + (f"\n\n<code>/collection {page + 1}</code> for more" if page < pages else ""),
        parse_mode="HTML",
    )


async def characters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
    async with async_session() as session:
        rows = (await session.execute(select(Character).order_by(Character.rarity, Character.name))).scalars().all()
    if not rows:
        await update.message.reply_text("No characters uploaded yet. Collector mods: /upload")
        return
    lines_all = [f"{_rarity_emoji(c.rarity)} <b>{escape_html(c.name)}</b> ({escape_html(c.anime or '?')}) — <code>{c.id}</code>" for c in rows]
    page_items, total, pages = paginate(lines_all, page, per_page=20)
    await update.message.reply_text(
        f"📖 <b>All Characters</b> ({total}) — page {page}/{pages}\n\n"
        + "\n".join(page_items) + (f"\n\n<code>/characters {page + 1}</code> for more" if page < pages else ""),
        parse_mode="HTML",
    )


async def fav_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /fav <character id> — see /collection for IDs")
        return
    char_id = int(context.args[0])
    async with async_session() as session:
        result = await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == update.effective_user.id, UserCharacter.character_id == char_id)
        )
        owned = result.scalars().all()
        if not owned:
            await update.message.reply_text("❌ You don't own that character.")
            return
        # Clear any existing favorite, then set this one
        existing_fav = await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == update.effective_user.id, UserCharacter.is_favorite.is_(True))
        )
        for row in existing_fav.scalars().all():
            row.is_favorite = False
        owned[0].is_favorite = True
        await session.commit()
    await update.message.reply_text("⭐ Favorite set.")


async def myprofile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with async_session() as session:
        total = (await session.execute(
            select(func.count()).select_from(UserCharacter).where(UserCharacter.user_id == user_id)
        )).scalar() or 0
        unique = (await session.execute(
            select(func.count(func.distinct(UserCharacter.character_id))).where(UserCharacter.user_id == user_id)
        )).scalar() or 0
        fav_result = await session.execute(
            select(Character).join(UserCharacter, UserCharacter.character_id == Character.id)
            .where(UserCharacter.user_id == user_id, UserCharacter.is_favorite.is_(True))
        )
        fav = fav_result.scalar_one_or_none()

    fav_line = f"⭐ Favorite: {escape_html(fav.name)}" if fav else "⭐ Favorite: none set (/fav <id>)"
    await update.message.reply_text(
        f"👤 <b>{escape_html(update.effective_user.first_name)}'s Collector Profile</b>\n\n"
        f"Total caught: <b>{total}</b>\nUnique characters: <b>{unique}</b>\n{fav_line}",
        parse_mode="HTML",
    )


@group_only
async def topcatchers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        result = await session.execute(
            select(UserCharacter.user_id, func.count().label("total"), User)
            .join(User, User.id == UserCharacter.user_id)
            .group_by(UserCharacter.user_id, User.id)
            .order_by(func.count().desc())
            .limit(10)
        )
        rows = result.all()
    if not rows:
        await update.message.reply_text("Nobody has caught anyone yet.")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Top Catchers</b>\n"]
    for i, (uid, total, user) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        name = user.first_name or user.username or str(uid)
        lines.append(f"{prefix} {escape_html(name)} — {total} caught")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ==================== TRADING & GIFTING ====================

@group_only
async def trade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Reply to the user you want to trade with.")
        return
    if len(context.args) != 2 or not all(a.isdigit() for a in context.args):
        await update.message.reply_text("Usage: reply to them + <code>/trade &lt;your char id&gt; &lt;their char id&gt;</code>", parse_mode="HTML")
        return

    my_id, their_id = int(context.args[0]), int(context.args[1])
    sender, receiver = update.effective_user, update.message.reply_to_message.from_user
    if sender.id == receiver.id:
        await update.message.reply_text("You can't trade with yourself.")
        return

    async with async_session() as session:
        mine = (await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == sender.id, UserCharacter.character_id == my_id)
        )).scalars().first()
        theirs = (await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == receiver.id, UserCharacter.character_id == their_id)
        )).scalars().first()
        if not mine:
            await update.message.reply_text("❌ You don't own that character.")
            return
        if not theirs:
            await update.message.reply_text(f"❌ {escape_html(receiver.first_name)} doesn't own that character.", parse_mode="HTML")
            return
        my_char = await session.get(Character, my_id)
        their_char = await session.get(Character, their_id)

    _pending_trades[(sender.id, receiver.id)] = {
        "my_char": my_id, "their_char": their_id,
        "expires": datetime.utcnow() + timedelta(minutes=settings.collector_trade_expiry_minutes),
    }
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"collector:trade_ok:{sender.id}:{receiver.id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"collector:trade_no:{sender.id}:{receiver.id}"),
    ]])
    await update.message.reply_text(
        f"🔄 {escape_html(sender.first_name)} offers <b>{escape_html(my_char.name)}</b> for "
        f"{escape_html(receiver.first_name)}'s <b>{escape_html(their_char.name)}</b>.\n"
        f"{escape_html(receiver.first_name)}, accept?",
        parse_mode="HTML", reply_markup=keyboard,
    )


async def _handle_trade_button(query, action: str, sender_id: int, receiver_id: int):
    if query.from_user.id != receiver_id:
        await query.answer("This trade isn't for you.", show_alert=False)
        return
    trade = _pending_trades.pop((sender_id, receiver_id), None)
    if not trade or datetime.utcnow() > trade["expires"]:
        await query.answer("This trade has expired.", show_alert=False)
        return

    if action == "trade_no":
        await query.answer("Declined.")
        await query.edit_message_text("❌ Trade declined.")
        return

    async with async_session() as session:
        mine = (await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == sender_id, UserCharacter.character_id == trade["my_char"])
        )).scalars().first()
        theirs = (await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == receiver_id, UserCharacter.character_id == trade["their_char"])
        )).scalars().first()
        if not mine or not theirs:
            await query.answer("One side no longer owns their character.", show_alert=True)
            await query.edit_message_text("❌ Trade fell through — a character changed hands since this was proposed.")
            return
        mine.user_id, theirs.user_id = receiver_id, sender_id
        await session.commit()

    await query.answer("Trade complete!")
    await query.edit_message_text("✅ Trade complete!")


@group_only
async def gift_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id, target_name = await resolve_target_user(update, context)
    char_id = next((int(a) for a in context.args if a.isdigit()), None)
    if not target_id or char_id is None:
        await update.message.reply_text("Usage: reply to someone (or /gift @username) + a character id, e.g. /gift 42")
        return
    if target_id == update.effective_user.id:
        await update.message.reply_text("❌ Can't gift to yourself.")
        return

    async with async_session() as session:
        owned = (await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == update.effective_user.id, UserCharacter.character_id == char_id)
        )).scalars().first()
        if not owned:
            await update.message.reply_text("❌ You don't own that character.")
            return
        owned.user_id = target_id
        owned.is_favorite = False
        char = await session.get(Character, char_id)
        await session.commit()

    await update.message.reply_text(f"🎁 Gifted <b>{escape_html(char.name)}</b> to {escape_html(target_name)}.", parse_mode="HTML")


# ==================== MODERATION ====================

@admin_only
async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/upload Name | Anime | rarity — reply to a photo, or attach one
    with the command as its caption."""
    if not await _is_collector_mod(update.effective_user.id):
        await update.message.reply_text("🚫 Collector moderators only.")
        return

    photo = None
    if update.message.photo:
        photo = update.message.photo[-1]
    elif update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]
    if not photo:
        await update.message.reply_text("Attach a photo (or reply to one) with caption: /upload Name | Anime | rarity")
        return

    raw = (update.message.text or update.message.caption or "")
    parts = raw.split(maxsplit=1)
    fields = parts[1].split("|") if len(parts) > 1 else []
    if len(fields) < 2:
        await update.message.reply_text("Usage: /upload Name | Anime | rarity (rarity optional, defaults to common)")
        return

    name = fields[0].strip()
    anime = fields[1].strip()
    rarity = fields[2].strip().lower() if len(fields) > 2 else "common"
    if rarity not in RARITY_EMOJIS:
        rarity = "common"

    file = await context.bot.get_file(photo.file_id)
    async with async_session() as session:
        char = Character(name=name, anime=anime, rarity=rarity, image_url=file.file_path, added_by=update.effective_user.id)
        session.add(char)
        await session.commit()
        char_id = char.id

    await update.message.reply_text(f"✅ Uploaded <b>{escape_html(name)}</b> — ID <code>{char_id}</code>", parse_mode="HTML")


@admin_only
async def delchar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_collector_mod(update.effective_user.id):
        await update.message.reply_text("🚫 Collector moderators only.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /delchar <character id>")
        return
    async with async_session() as session:
        char = await session.get(Character, int(context.args[0]))
        if not char:
            await update.message.reply_text("❌ No character with that ID.")
            return
        await session.delete(char)
        await session.commit()
    await update.message.reply_text("🗑 Character deleted (existing copies in collections are kept).")


@admin_only
async def addmod_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id, target_name = await resolve_target_user(update, context)
    if not target_id:
        await update.message.reply_text("Reply to a user, or /addmod @username")
        return
    async with async_session() as session:
        if await session.get(CollectorModerator, target_id):
            await update.message.reply_text(f"{escape_html(target_name)} is already a collector mod.", parse_mode="HTML")
            return
        session.add(CollectorModerator(user_id=target_id, added_by=update.effective_user.id))
        await session.commit()
    await update.message.reply_text(f"✅ {escape_html(target_name)} can now /upload and /delchar.", parse_mode="HTML")


@admin_only
async def removemod_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id, target_name = await resolve_target_user(update, context)
    if not target_id:
        await update.message.reply_text("Reply to a user, or /removemod @username")
        return
    async with async_session() as session:
        mod = await session.get(CollectorModerator, target_id)
        if not mod:
            await update.message.reply_text(f"{escape_html(target_name)} isn't a collector mod.", parse_mode="HTML")
            return
        await session.delete(mod)
        await session.commit()
    await update.message.reply_text(f"❌ {escape_html(target_name)} is no longer a collector mod.", parse_mode="HTML")


async def mods_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        rows = (await session.execute(select(CollectorModerator))).scalars().all()
    if not rows:
        await update.message.reply_text("No collector moderators yet (bot sudoers can always /upload).")
        return
    lines = "\n".join(f"• <code>{r.user_id}</code>" for r in rows)
    await update.message.reply_text(f"🛡 <b>Collector moderators</b>\n{lines}", parse_mode="HTML")


@group_only
@admin_only
async def setspawnrate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit() or int(context.args[0]) < 5:
        await update.message.reply_text("Usage: /setspawnrate <messages ≥ 5>")
        return
    rate = int(context.args[0])
    async with async_session() as session:
        chat = await session.get(Chat, update.effective_chat.id)
        if chat is None:
            chat = Chat(id=update.effective_chat.id, type=update.effective_chat.type)
            session.add(chat)
        chat.collector_spawn_rate = rate
        await session.commit()
    await update.message.reply_text(f"⚙️ A character will now spawn roughly every {rate} messages.")


# ==================== GIVEAWAYS ====================

@group_only
@admin_only
async def giveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2 or not context.args[0].isdigit() or not context.args[1].isdigit():
        await update.message.reply_text("Usage: /giveaway <coins> <minutes>")
        return
    coins, minutes = int(context.args[0]), int(context.args[1])
    async with async_session() as session:
        ga = Giveaway(
            chat_id=update.effective_chat.id, prize_coins=coins,
            created_by=update.effective_user.id, ends_at=datetime.utcnow() + timedelta(minutes=minutes),
        )
        session.add(ga)
        await session.commit()
        ga_id = ga.id

    await update.message.reply_text(
        f"🎁 <b>Giveaway started!</b> {coins:,} 🪙 — first to /claim {ga_id} wins. Ends in {minutes}m.",
        parse_mode="HTML",
    )
    if context.job_queue:
        context.job_queue.run_once(_end_giveaway_job, when=minutes * 60, data={"giveaway_id": ga_id})


async def _end_giveaway_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    ga_id = context.job.data["giveaway_id"]
    async with async_session() as session:
        ga = await session.get(Giveaway, ga_id)
        if not ga or ga.ended:
            return
        ga.ended = True
        await session.commit()
        chat_id, claimed_by = ga.chat_id, ga.claimed_by
    if not claimed_by:
        try:
            await context.bot.send_message(chat_id, f"🎁 Giveaway #{ga_id} ended — nobody claimed it in time.")
        except Exception:
            pass


@group_only
async def claim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /claim <giveaway id>")
        return
    ga_id = int(context.args[0])
    async with async_session() as session:
        ga = await session.get(Giveaway, ga_id)
        if not ga or ga.chat_id != update.effective_chat.id:
            await update.message.reply_text("❌ No such giveaway here.")
            return
        if ga.ended or datetime.utcnow() > ga.ends_at:
            await update.message.reply_text("❌ That giveaway has already ended.")
            return
        ga.ended = True
        ga.claimed_by = update.effective_user.id
        await session.commit()
        coins = ga.prize_coins

    new_balance = await add_coins(update.effective_chat.id, update.effective_user.id, coins)
    await update.message.reply_text(
        f"🎉 {escape_html(update.effective_user.first_name)} claimed {coins:,} 🪙! (balance: {new_balance:,})",
        parse_mode="HTML",
    )


@group_only
@admin_only
async def endgiveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /endgiveaway <giveaway id>")
        return
    async with async_session() as session:
        ga = await session.get(Giveaway, int(context.args[0]))
        if not ga or ga.chat_id != update.effective_chat.id or ga.ended:
            await update.message.reply_text("❌ No active giveaway with that ID here.")
            return
        ga.ended = True
        await session.commit()
    await update.message.reply_text("🛑 Giveaway ended early.")


# ==================== CALLBACK ROUTER ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data[len("collector:"):]
    parts = data.split(":")
    action = parts[0]
    if action in ("trade_ok", "trade_no"):
        await _handle_trade_button(query, action, int(parts[1]), int(parts[2]))
        return
    await query.answer()


def register(app):
    if not settings.enable_collector:
        return
    app.add_handler(CommandHandler("spawn", spawn_cmd))
    app.add_handler(CommandHandler("grab", grab_cmd))
    app.add_handler(CommandHandler("collection", collection_cmd))
    app.add_handler(CommandHandler("characters", characters_cmd))
    app.add_handler(CommandHandler("fav", fav_cmd))
    app.add_handler(CommandHandler("myprofile", myprofile_cmd))
    app.add_handler(CommandHandler("topcatchers", topcatchers_cmd))
    app.add_handler(CommandHandler("trade", trade_cmd))
    app.add_handler(CommandHandler("gift", gift_cmd))
    app.add_handler(CommandHandler("upload", upload_cmd))
    app.add_handler(CommandHandler("delchar", delchar_cmd))
    app.add_handler(CommandHandler("addmod", addmod_cmd))
    app.add_handler(CommandHandler("removemod", removemod_cmd))
    app.add_handler(CommandHandler("mods", mods_cmd))
    app.add_handler(CommandHandler("setspawnrate", setspawnrate_cmd))
    app.add_handler(CommandHandler("giveaway", giveaway_cmd))
    app.add_handler(CommandHandler("endgiveaway", endgiveaway_cmd))
    app.add_handler(CommandHandler("claim", claim_cmd))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^collector:"))

    # Distinct group — see group_mgmt.py's register() for why every
    # catch-all text handler needs its own.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, spawn_listener), group=7)
