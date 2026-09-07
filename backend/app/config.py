from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # =====================================================
    # APP
    # =====================================================

    app_name: str = "AIFlow"

    app_env: str = "development"

    # Vestigial: nothing in the app currently reads this. It is NOT wired
    # to FastAPI/Starlette's own debug mode (verbose tracebacks to the
    # client), which is hardcoded off in main.py's `FastAPI(...)` call
    # regardless of this value - that is the actually security-relevant
    # setting, and it is off in every environment on purpose.
    debug: bool = True

    app_url: str = "http://localhost:8000"

    frontend_url: str = "http://localhost:5173"

    # Plain Python logging level name (DEBUG/INFO/WARNING/ERROR). Format
    # (JSON vs. human-readable) is derived from app_env, not configured
    # separately - see app/logging_config.py.
    log_level: str = "INFO"

    # =====================================================
    # DATABASE
    # =====================================================

    database_url: str

    # =====================================================
    # JWT
    # =====================================================

    jwt_secret: str

    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 15

    refresh_token_expire_days: int = 30

    # =====================================================
    # AI
    # =====================================================

    llm_api_key: str

    llm_base_url: str = "https://api.openai.com/v1"

    llm_model: str = "gpt-4o-mini"

    # =====================================================
    # NOTIFICATIONS (all optional — dev falls back to logging)
    # =====================================================

    # Email (SMTP). For production use Resend/SendGrid SMTP creds.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # SMS (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_sms_from: str = ""

    # WhatsApp (Meta Cloud API)
    whatsapp_phone_id: str = ""
    whatsapp_token: str = ""

    # =====================================================
    # CALENDAR (Google OAuth — optional)
    # =====================================================

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    # =====================================================
    # WHATSAPP / INSTAGRAM CHANNELS (Meta — optional)
    #
    # These belong to AIFlow's own Meta App configuration (one per
    # deployment), NOT to any one tenant - that's why they're env vars
    # rather than per-business database rows. A business's own connection
    # (which WhatsApp number / Instagram account, and the token to send as
    # it) is per-tenant data, stored in ChannelCredential instead - see
    # app/models.py and app/services/channels/.
    #
    # WHATSAPP_APP_SECRET / INSTAGRAM_APP_SECRET: from Meta App Dashboard →
    # App Settings → Basic → App Secret. Used to verify the
    # X-Hub-Signature-256 header on every inbound webhook - this is what
    # proves a webhook request actually came from Meta and not an
    # impersonator, so it must be set before any real traffic is trusted.
    #
    # WHATSAPP_WEBHOOK_VERIFY_TOKEN / INSTAGRAM_WEBHOOK_VERIFY_TOKEN: an
    # arbitrary string you choose yourself and enter in Meta's webhook
    # subscription setup (App Dashboard → Webhooks → Configure) - Meta
    # echoes it back on the one-time verification handshake so this app can
    # confirm it's really being configured by you.
    # =====================================================

    whatsapp_app_secret: str = ""
    whatsapp_webhook_verify_token: str = ""

    instagram_app_secret: str = ""
    instagram_webhook_verify_token: str = ""

    # =====================================================
    # CORS
    # =====================================================

    allowed_origins: str = "http://localhost:5173"

    @field_validator("allowed_origins")
    @classmethod
    def clean_origins(cls, value: str):

        return ",".join(
            origin.strip()
            for origin in value.split(",")
            if origin.strip()
        )

    def cors_origins(self) -> list[str]:

        return self.allowed_origins.split(",")


@lru_cache
def get_settings():

    return Settings()