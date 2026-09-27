# app/config.py
import os

from dotenv import load_dotenv

load_dotenv()  # Loads .env into environment variables (no-op on Railway)


def _normalize_db_url(url: str) -> str:
    """
    Force the postgresql:// scheme that SQLAlchemy 2.x requires.

    Railway hands out postgres:// URLs - that is what ${{Postgres.DATABASE_URL}}
    expands to - and SQLAlchemy 2.x refuses the shorter form outright. Rewriting
    it here means the value can be pasted or referenced straight from Railway
    without anyone remembering to edit the prefix.
    """
    if url and url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


class Settings:
    DATABASE_URL = _normalize_db_url(os.getenv("DATABASE_URL", ""))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Origins allowed to call the API from a browser. The bundled widget is
    # served by this same app, so it needs no entry here; this is for embedding
    # the chat on another host, such as the marketing site.
    ALLOWED_ORIGINS = [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS",
            "https://teep.africa,https://www.teep.africa,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if o.strip()
    ]

    def validate(self) -> None:
        """
        Fail at startup rather than per request.

        Without this a deploy with a missing variable looks healthy - the
        container boots, /health returns OK - and only breaks when a customer
        sends the first message.
        """
        missing = [
            name
            for name in ("DATABASE_URL", "OPENAI_API_KEY")
            if not getattr(self, name)
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". Set them in the Railway service variables (or .env locally)."
            )


settings = Settings()
