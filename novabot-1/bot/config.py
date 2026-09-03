"""
NovaBot Unified Configuration — Pydantic Settings v2.

Merges configuration that used to live in four separate projects:
  - nova_guard_bot   (moderation core, AI plugin, anti-spam)
  - harmony-music-bot (live voice-chat music engine)
  - nanora_bot       (sarcastic personality / banter layer)
  - font_bot_ultimate.py (Unicode font styling)

Auto-loads from environment variables and a local .env file. Every field
has a sensible default except BOT_TOKEN and OWNER_ID, so the bot can run
locally with a minimal .env.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Core Bot ──────────────────────────────────────────────────────
    bot_token: str = Field(..., alias="BOT_TOKEN")
    owner_id: int = Field(..., alias="OWNER_ID")
    admin_ids: List[int] = Field(default_factory=list, alias="ADMIN_IDS")
    debug: bool = Field(False, alias="DEBUG")

    # ── Server (webhook mode; omit WEBHOOK_URL to use polling) ─────────
    webhook_url: Optional[str] = Field(None, alias="WEBHOOK_URL")
    webhook_port: int = Field(8443, alias="WEBHOOK_PORT")

    # ── Database ─────────────────────────────────────────────────────
    # Defaults to a local SQLite file so the bot runs with zero external
    # services. Point this at postgresql+asyncpg://... for production.
    database_url: str = Field("sqlite+aiosqlite:///./data/novabot.db", alias="DATABASE_URL")
    redis_url: Optional[str] = Field(None, alias="REDIS_URL")  # optional cache layer, not required

    # ── AI Providers (the /ai /chat /code /summarize /imagine plugin) ──
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(None, alias="GOOGLE_API_KEY")
    default_ai_model: str = "gpt-4o-mini"

    # ── External APIs ────────────────────────────────────────────────
    youtube_api_key: Optional[str] = Field(None, alias="YOUTUBE_API_KEY")
    tmdb_api_key: Optional[str] = Field(None, alias="TMDB_API_KEY")
    weather_api_key: Optional[str] = Field(None, alias="WEATHER_API_KEY")
    news_api_key: Optional[str] = Field(None, alias="NEWS_API_KEY")
    genius_api_key: Optional[str] = Field(None, alias="GENIUS_API_KEY")

    # ── Anti-Spam Heuristics ─────────────────────────────────────────
    antiflood_threshold: int = 5
    antiflood_interval: int = 6
    antiflood_ban_duration: int = 300
    spam_ml_threshold: float = 0.75

    # ── Live Music — voice-chat streaming (formerly harmony-music-bot) ─
    # Streaming audio INTO a voice chat needs an MTProto session on top
    # of the normal Bot API token — the HTTP Bot API alone cannot join
    # group calls. Get MUSIC_API_ID / MUSIC_API_HASH from my.telegram.org
    # (same bot account, just a second login method). Live music is
    # automatically disabled if these aren't set; /music and /yt (file
    # download + send) keep working either way.
    music_api_id: Optional[int] = Field(None, alias="MUSIC_API_ID")
    music_api_hash: Optional[SecretStr] = Field(None, alias="MUSIC_API_HASH")
    music_session_name: str = Field("novabot_music", alias="MUSIC_SESSION_NAME")
    ffmpeg_path: str = Field("/usr/bin/ffmpeg", alias="FFMPEG_PATH")
    music_workers: int = Field(8, alias="MUSIC_WORKERS", ge=1, le=64)
    music_max_connections: int = Field(100, alias="MUSIC_MAX_CONNECTIONS", ge=1)
    max_queue_size: int = Field(2000, alias="MAX_QUEUE_SIZE", ge=1)
    default_group_volume: int = Field(100, alias="DEFAULT_GROUP_VOLUME", ge=1, le=1000)
    max_group_volume: int = Field(200, alias="MAX_GROUP_VOLUME", ge=1, le=1000)

    # ── Multi-assistant scaling (from YukkiMusicBot, adapted) ────────
    # One assistant can only be in a limited number of voice chats at
    # once, so YukkiMusicBot spreads load across up to 5 assistants —
    # but its assistants are full user accounts logged in via phone
    # number (Pyrogram "string sessions"), which is a materially
    # different, ToS-grayer pattern than the bot-token MTProto approach
    # used everywhere else in this project. Extra assistants here are
    # instead extra BOT accounts (their own BOT_TOKEN from BotFather,
    # sharing MUSIC_API_ID/MUSIC_API_HASH) — same scaling benefit,
    # same account type as the primary one. Leave blank to run with a
    # single assistant.
    music_extra_bot_tokens: List[str] = Field(default_factory=list, alias="MUSIC_EXTRA_BOT_TOKENS")
    assistant_auto_leave_seconds: int = Field(0, alias="ASSISTANT_AUTO_LEAVE_SECONDS", ge=0)  # 0 = disabled

    # ── Multi-platform music sources (from YukkiMusicBot) ────────────
    # Spotify/Apple Music/Resso links resolve to title+artist metadata
    # (via their own public API/page metadata — never their audio, which
    # isn't legally redistributable this way), then search & stream the
    # match from YouTube, same as harmony's original approach. SoundCloud
    # needs no extra config — yt-dlp streams it directly.
    spotify_client_id: Optional[str] = Field(None, alias="SPOTIFY_CLIENT_ID")
    spotify_client_secret: Optional[SecretStr] = Field(None, alias="SPOTIFY_CLIENT_SECRET")

    # ── Playlists & downloads (from YukkiMusicBot) ───────────────────
    playlist_fetch_limit: int = Field(25, alias="PLAYLIST_FETCH_LIMIT", ge=1, le=200)
    server_playlist_limit: int = Field(30, alias="SERVER_PLAYLIST_LIMIT", ge=1)
    song_download_duration_limit_min: int = Field(180, alias="SONG_DOWNLOAD_DURATION_LIMIT", ge=1)

    # ── Video calls (from YukkiMusicBot) — opt-in per chat via Chat.
    # video_enabled; this just caps how many can run at once bot-wide. ─
    video_stream_limit: int = Field(3, alias="VIDEO_STREAM_LIMIT", ge=0)

    # ── Cleanmode default (per-chat toggle, see Chat.cleanmode_enabled) ─
    cleanmode_delete_minutes: int = Field(5, alias="CLEANMODE_DELETE_MINUTES", ge=1)

    # ── Access control (from YukkiMusicBot) ──────────────────────────
    # Global default for private-bot-mode; the live value is DB-backed
    # (BotConfig, toggleable at runtime via /privatemode without a
    # restart) and seeded from this on first run.
    private_bot_mode: bool = Field(False, alias="PRIVATE_BOT_MODE")

    # ── Personality layer (formerly nanora_bot) ─────────────────────
    personality_cooldown_seconds: float = Field(1.5, alias="PERSONALITY_COOLDOWN_SECONDS")
    personality_max_context: int = Field(20, alias="PERSONALITY_MAX_CONTEXT")
    personality_sarcasm_probability: float = Field(0.85, alias="PERSONALITY_SARCASM_PROBABILITY")
    # DMs default to personality-on (closest to nanora's original standalone
    # behaviour); existing moderation groups default to OFF so NovaBot
    # doesn't suddenly start bantering in a community that didn't ask for
    # it — admins opt in with /personality on.
    personality_default_dm: bool = Field(True, alias="PERSONALITY_DEFAULT_DM")
    personality_default_group: bool = Field(False, alias="PERSONALITY_DEFAULT_GROUP")

    # ── Font plugin (formerly font_bot_ultimate.py) ─────────────────
    # Off by default — the original bot gated every command behind
    # forced-channel-membership; that's a font-bot-specific growth tactic,
    # not something a moderation/AI/music bot's users should be surprised
    # by. Turn it on and set FONT_GATE_CHANNEL to restore that behaviour.
    font_gate_enabled: bool = Field(False, alias="FONT_GATE_ENABLED")
    font_gate_channel: Optional[str] = Field(None, alias="FONT_GATE_CHANNEL")
    font_rate_limit_window: int = Field(60, alias="FONT_RATE_LIMIT_WINDOW")
    font_rate_limit_max: int = Field(20, alias="FONT_RATE_LIMIT_MAX")

    # ── Feature toggles ──────────────────────────────────────────────
    enable_ai: bool = True
    enable_music_download: bool = True
    enable_live_music: bool = True
    enable_anime: bool = True
    enable_captcha: bool = True
    enable_federation: bool = True
    enable_personality: bool = True
    enable_fonts: bool = True
    enable_economy: bool = True
    enable_games: bool = True
    enable_scheduling: bool = True
    enable_automod: bool = True
    enable_playlists: bool = True

    # ── Economy & Leveling ───────────────────────────────────────────
    economy_xp_per_message: int = Field(5, alias="ECONOMY_XP_PER_MESSAGE", ge=0)
    economy_xp_cooldown_seconds: int = Field(60, alias="ECONOMY_XP_COOLDOWN_SECONDS", ge=0)
    economy_starting_balance: int = Field(100, alias="ECONOMY_STARTING_BALANCE", ge=0)
    economy_daily_min: int = Field(50, alias="ECONOMY_DAILY_MIN", ge=0)
    economy_daily_max: int = Field(150, alias="ECONOMY_DAILY_MAX", ge=0)

    # ── Games ─────────────────────────────────────────────────────
    games_min_bet: int = Field(10, alias="GAMES_MIN_BET", ge=1)
    games_max_bet: int = Field(5000, alias="GAMES_MAX_BET", ge=1)

    # ── Character Collector (from anime_collector_bot / anime_catcher_bot
    # / WAIFU-HUSBANDO-CATCHER) ──────────────────────────────────────
    enable_collector: bool = True
    collector_default_spawn_rate: int = Field(50, alias="COLLECTOR_SPAWN_RATE", ge=5)  # messages between spawns
    collector_trade_expiry_minutes: int = Field(5, alias="COLLECTOR_TRADE_EXPIRY_MINUTES", ge=1)
    collector_catch_reward_coins: int = Field(20, alias="COLLECTOR_CATCH_REWARD_COINS", ge=0)

    # ── Auto-Moderation defaults (per-chat overridable) ─────────────
    default_warn_limit: int = Field(3, alias="DEFAULT_WARN_LIMIT", ge=1)
    default_warn_action: str = Field("mute", alias="DEFAULT_WARN_ACTION")  # mute|kick|ban
    antiraid_default_join_threshold: int = Field(5, alias="ANTIRAID_JOIN_THRESHOLD", ge=2)
    antiraid_default_join_window: int = Field(10, alias="ANTIRAID_JOIN_WINDOW", ge=1)

    # ── Dashboard heartbeat (the bot writes stats; the dashboard reads
    # them — they don't share a process, see dashboard/) ─────────────
    dashboard_heartbeat_interval: int = Field(30, alias="DASHBOARD_HEARTBEAT_INTERVAL", ge=5)

    # ── Localization ─────────────────────────────────────────────────
    default_language: str = "en"
    supported_languages: List[str] = ["en", "es", "ru", "id", "hi", "ar", "zh"]

    # ── Paths ────────────────────────────────────────────────────────
    data_dir: Path = Field(default=Path("./data"))
    sessions_dir: Path = Field(default=Path("./sessions"))
    downloads_dir: Path = Field(default=Path("./data/downloads"))

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v):
        """Accept 'comma,separated,ids' from .env as well as a JSON list."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                import json
                return json.loads(stripped)
            return [int(x.strip()) for x in stripped.split(",") if x.strip()]
        return v

    @field_validator("music_extra_bot_tokens", mode="before")
    @classmethod
    def _parse_extra_bot_tokens(cls, v):
        """Accept 'token1,token2' from .env as well as a JSON list."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                import json
                return json.loads(stripped)
            return [t.strip() for t in stripped.split(",") if t.strip()]
        return v

    @field_validator("data_dir", "sessions_dir", "downloads_dir", mode="before")
    @classmethod
    def _ensure_path(cls, v):
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def live_music_configured(self) -> bool:
        """Whether enough credentials are present to start the voice-chat engine."""
        return bool(self.enable_live_music and self.music_api_id and self.music_api_hash)

    def is_admin_id(self, user_id: int) -> bool:
        """True if user_id is the owner or in ADMIN_IDS."""
        return user_id == self.owner_id or user_id in self.admin_ids


settings = Settings()


def get_settings() -> Settings:
    """Compatibility shim for modules ported from harmony-music-bot, which
    called `get_settings()` instead of importing the module-level singleton."""
    return settings
