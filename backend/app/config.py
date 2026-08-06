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

    debug: bool = True

    app_url: str = "http://localhost:8000"

    frontend_url: str = "http://localhost:5173"

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