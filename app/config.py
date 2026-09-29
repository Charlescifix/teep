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

    # Per-IP caps on POST /api/chat, putting a ceiling on what one caller can
    # spend in OpenAI credits. Set either to 0 to switch that window off.
    #
    # The per-minute figure is looser than one person needs on purpose: mobile
    # carriers put many subscribers behind a single address, so an allowance
    # sized for one customer would throttle everyone sharing that IP.
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "50"))

    # How many proxies sit in front of the app, used to pick the trustworthy
    # entry out of X-Forwarded-For. 1 is correct for Railway's edge; raise it
    # only if you put another proxy or CDN in front of that.
    TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "1"))

    # How much of the caller's address the limiter counts on. The default /24
    # means 152.233.29.1 and 152.233.29.5 share one allowance instead of taking
    # one each, which is how a flood from a single range walked past the cap.
    #
    # Widening the bucket also groups more real strangers together - see the
    # note on RATE_LIMIT_PER_MINUTE above - so 32 and 128 restore per-address
    # counting if these limits start catching genuine users.
    RATE_LIMIT_IPV4_PREFIX = int(os.getenv("RATE_LIMIT_IPV4_PREFIX", "24"))
    RATE_LIMIT_IPV6_PREFIX = int(os.getenv("RATE_LIMIT_IPV6_PREFIX", "64"))

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

        # A prefix outside its family's range would make every call raise from
        # inside the limiter, i.e. a 503 per request, so catch it at boot.
        for name, ceiling in (
            ("RATE_LIMIT_IPV4_PREFIX", 32),
            ("RATE_LIMIT_IPV6_PREFIX", 128),
        ):
            value = getattr(self, name)
            if not 0 <= value <= ceiling:
                raise RuntimeError(
                    f"{name} must be between 0 and {ceiling}, got {value}."
                )


settings = Settings()
