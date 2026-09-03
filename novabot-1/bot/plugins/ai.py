"""
Advanced AI Plugin supporting OpenAI, Anthropic, and Google Gemini.
Features: chat, summarize, imagine (DALL-E), code assistant, persona memory.
"""
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from bot.config import settings
from bot.core.database import async_session, AIConversation, User
from bot.utils.helpers import escape_html
from sqlalchemy import select, desc
import openai
import httpx

# Initialize clients conditionally — only providers with a key set do anything.
_openai_client = None
if settings.openai_api_key:
    _openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

_anthropic_client = None
if settings.anthropic_api_key:
    import anthropic
    _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

_gemini_configured = False
if settings.google_api_key:
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    _gemini_configured = True


def _pick_provider(model: str) -> str:
    """Route a model name to a provider, falling back to whichever
    provider actually has a key configured if the requested one doesn't."""
    if "claude" in model and _anthropic_client:
        return "anthropic"
    if "gemini" in model and _gemini_configured:
        return "google"
    if "gpt" in model and _openai_client:
        return "openai"
    # Requested provider isn't configured — fall back to whatever is.
    if _openai_client:
        return "openai"
    if _anthropic_client:
        return "anthropic"
    if _gemini_configured:
        return "google"
    return "none"


async def _get_ai_response(user_id: int, text: str, model: str = None) -> str:
    model = model or settings.default_ai_model

    # Fetch recent history
    async with async_session() as session:
        result = await session.execute(
            select(AIConversation)
            .where(AIConversation.user_id == user_id)
            .order_by(desc(AIConversation.id))
            .limit(10)
        )
        history = result.scalars().all()
        history.reverse()

    system_prompt = "You are NovaBot AI, a helpful, witty, and concise assistant."
    async with async_session() as session:
        user_row = await session.get(User, user_id)
        if user_row and user_row.ai_persona:
            system_prompt = user_row.ai_persona

    turns = [{"role": h.role, "content": h.content} for h in history]
    turns.append({"role": "user", "content": text})

    provider = _pick_provider(model)

    if provider == "openai":
        messages = [{"role": "system", "content": system_prompt}, *turns]
        resp = await _openai_client.chat.completions.create(
            model=model if "gpt" in model else settings.default_ai_model,
            messages=messages, max_tokens=800, temperature=0.7,
        )
        return resp.choices[0].message.content

    if provider == "anthropic":
        # Anthropic's Messages API takes the system prompt separately, not
        # as a role inside the messages array.
        resp = await _anthropic_client.messages.create(
            model=model if "claude" in model else "claude-3-5-sonnet-latest",
            max_tokens=800,
            system=system_prompt,
            messages=turns,
        )
        return resp.content[0].text

    if provider == "google":
        import google.generativeai as genai
        transcript = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
        gemini_model = genai.GenerativeModel(
            model if "gemini" in model else "gemini-1.5-flash",
            system_instruction=system_prompt,
        )
        resp = await gemini_model.generate_content_async(transcript)
        return resp.text

    return "🤖 AI is not configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY in .env"


async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = " ".join(context.args) or (update.message.reply_to_message.text if update.message.reply_to_message else None)
    if not text:
        await update.message.reply_text("Usage: /ai <question> or reply to a message")
        return

    msg = await update.message.reply_text("🧠 Thinking...")
    try:
        response = await _get_ai_response(user.id, text)
        # Store conversation
        async with async_session() as session:
            session.add(AIConversation(user_id=user.id, role="user", content=text, model=settings.default_ai_model))
            session.add(AIConversation(user_id=user.id, role="assistant", content=response, model=settings.default_ai_model))
            await session.commit()

        await msg.edit_text(f"<b>🤖 NovaBot AI</b>\n{escape_html(response)}", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ AI Error: {e}")


async def ai_imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _openai_client:
        await update.message.reply_text("❌ OpenAI not configured.")
        return
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Usage: /imagine <description>")
        return

    msg = await update.message.reply_text("🎨 Generating image...")
    try:
        resp = await _openai_client.images.generate(
            model="dall-e-3", prompt=prompt, n=1, size="1024x1024"
        )
        url = resp.data[0].url
        await msg.delete()
        await update.message.reply_photo(url, caption=f"🎨 <b>Prompt:</b> <i>{escape_html(prompt)}</i>", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def ai_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    if not reply or not reply.text:
        await update.message.reply_text("Reply to a long text to summarize.")
        return

    msg = await update.message.reply_text("📝 Summarizing...")
    prompt = f"Summarize the following text concisely:\n\n{reply.text[:3000]}"
    try:
        response = await _get_ai_response(update.effective_user.id, prompt, model="gpt-4o-mini")
        await msg.edit_text(f"<b>📝 Summary</b>\n{escape_html(response)}", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def ai_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /code <programming question>")
        return
    prompt = f"You are an expert programmer. Provide clean, commented code with explanation:\n\n{text}"
    msg = await update.message.reply_text("💻 Coding...")
    try:
        response = await _get_ai_response(update.effective_user.id, prompt)
        await msg.edit_text(f"<b>💻 Code Assistant</b>\n<pre>{escape_html(response)}</pre>", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def persona_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    async with async_session() as session:
        user_row = await session.get(User, update.effective_user.id)
        if user_row is None:
            user_row = User(id=update.effective_user.id)
            session.add(user_row)
        if not text or text.lower() == "reset":
            user_row.ai_persona = None
            await session.commit()
            await update.message.reply_text("🎭 Persona reset to the default assistant.")
            return
        user_row.ai_persona = text
        await session.commit()
    await update.message.reply_text(
        f"🎭 Persona set. /ai and /chat will now respond as:\n<i>{escape_html(text)}</i>\n\n"
        f"(<code>/persona reset</code> to go back to default)",
        parse_mode="HTML",
    )


async def see_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vision — reply to a photo (or attach one directly) with /see [question]."""
    import base64

    provider = _pick_provider("")
    if provider == "none":
        await update.message.reply_text("❌ AI is not configured.")
        return

    photo = None
    if update.message.photo:
        photo = update.message.photo[-1]
    elif update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]
    if not photo:
        await update.message.reply_text("Reply to a photo (or attach one) with /see [optional question]")
        return

    question = " ".join(context.args) or "Describe this image in detail."
    msg = await update.message.reply_text("👁️ Looking...")

    try:
        file = await context.bot.get_file(photo.file_id)
        raw = bytes(await file.download_as_bytearray())
        b64 = base64.b64encode(raw).decode()

        if provider == "openai":
            resp = await _openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }],
                max_tokens=600,
            )
            answer = resp.choices[0].message.content
        elif provider == "anthropic":
            resp = await _anthropic_client.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=600,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        {"type": "text", "text": question},
                    ],
                }],
            )
            answer = resp.content[0].text
        else:  # google
            import google.generativeai as genai
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = await model.generate_content_async([question, {"mime_type": "image/jpeg", "data": raw}])
            answer = resp.text

        await msg.edit_text(f"<b>👁️ Vision</b>\n{escape_html(answer)}", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def transcribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Voice-note transcription via OpenAI Whisper — reply to a voice/audio message."""
    if not _openai_client:
        await update.message.reply_text("❌ Transcription needs OPENAI_API_KEY.")
        return

    reply = update.message.reply_to_message
    media = None
    if reply:
        media = reply.voice or reply.audio
    if not media:
        await update.message.reply_text("Reply to a voice message or audio file with /transcribe")
        return

    msg = await update.message.reply_text("🎙️ Transcribing...")
    try:
        file = await context.bot.get_file(media.file_id)
        raw = bytes(await file.download_as_bytearray())
        transcript = await _openai_client.audio.transcriptions.create(
            model="whisper-1", file=("audio.ogg", raw),
        )
        await msg.edit_text(f"<b>🎙️ Transcript</b>\n{escape_html(transcript.text)}", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


def register(app):
    app.add_handler(CommandHandler("ai", ai_chat))
    app.add_handler(CommandHandler("chat", ai_chat))
    app.add_handler(CommandHandler("imagine", ai_imagine))
    app.add_handler(CommandHandler("summarize", ai_summarize))
    app.add_handler(CommandHandler("code", ai_code))
    app.add_handler(CommandHandler("persona", persona_cmd))
    app.add_handler(CommandHandler("see", see_cmd))
    app.add_handler(CommandHandler("transcribe", transcribe_cmd))
