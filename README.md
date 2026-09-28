# TEEP RAG Chatbot

A Retrieval-Augmented Generation support assistant for TEEP. FastAPI serves both
the JSON API and the chat widget, answering questions from a knowledge base
stored in Postgres with pgvector.

## How it works

1. `data/teep_knowledge_base.md` holds the knowledge base, one `##` section per
   topic.
2. `scripts/insert_sample_docs.py` chunks it one-per-section, embeds each chunk
   with OpenAI, and stores it in the `documents` table as a `vector(1536)`.
3. On each question, `app/services/retrieval_service.py` embeds the query and
   lets Postgres rank chunks by cosine distance through an HNSW index.
4. `app/services/llm_service.py` passes the top 3 chunks to the chat model,
   under a prompt that keeps answers grounded in those chunks.

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Postgres connection string. A `postgres://` URL is rewritten to `postgresql://` automatically, so Railway's value works as-is. |
| `OPENAI_API_KEY` | yes | Used for both embeddings and chat completions. |
| `ALLOWED_ORIGINS` | no | Comma-separated CORS origins. Defaults to the TEEP domains plus localhost. Only needed when the widget is embedded on another host. |
| `RATE_LIMIT_PER_MINUTE` | no | Per-IP cap on `/api/chat`. Defaults to 6. `0` disables this window. |
| `RATE_LIMIT_PER_HOUR` | no | Per-IP cap on `/api/chat`. Defaults to 40. `0` disables this window. |
| `TRUSTED_PROXY_HOPS` | no | Proxies in front of the app, used to read `X-Forwarded-For`. Defaults to 1, which is correct for Railway. |
| `PORT` | no | Set by Railway. Defaults to 8000 locally. |

The app validates the two required variables at startup and exits with a message
naming any that are missing, rather than failing on the first customer message.

## Running locally

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: .venv/bin/pip
cp .env.example .env                            # then fill in the two values
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

- Chat widget: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Seeding the knowledge base

One-time, against an empty database:

```bash
python -m scripts.db_reset            # creates tables + the HNSW index
python -m scripts.insert_sample_docs  # embeds and inserts every section
```

After editing `data/teep_knowledge_base.md`, re-run the seed alone. It replaces
the existing rows by default, so a stale version is not left behind competing for
the top-k slots. Pass `--append` to keep them.

**`db_reset` drops `documents` and `chats`.** Only run it when you intend to
rebuild from scratch.

## API

`POST /api/chat` accepts the question either way:

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_query": "How long do refunds take?"}'

curl -X POST 'http://127.0.0.1:8000/api/chat?user_query=How+long+do+refunds+take'
```

```json
{
  "query": "How long do refunds take?",
  "answer": "Refunds are processed within 5 business days after approval. ..."
}
```

The retrieved chunks are deliberately not in the response — the endpoint is
public through the widget, and returning them let anyone read the knowledge
base out of the browser's network tab. Which chunks were used, and their
scores, are logged server-side instead.

Each call is independent — there is no conversation history, so follow-up
questions do not see earlier turns.

## Deploying to Railway

The repo is configured for Railway's Nixpacks builder: `railway.json` sets the
start command and a `/health` check, `.python-version` pins Python 3.11, and the
`Procfile` binds `$PORT`.

1. Create a Railway project from this repo.
2. Add a Postgres database to the project. pgvector ships with Railway's image
   but is not enabled by default — `scripts/db_reset.py` runs
   `CREATE EXTENSION IF NOT EXISTS vector` for you.
3. Set the service variables:
   - `DATABASE_URL` — reference the database with `${{Postgres.DATABASE_URL}}`
   - `OPENAI_API_KEY`
   - `ALLOWED_ORIGINS` if the widget will be embedded off-domain
4. Deploy, then seed **once** against that database:
   ```bash
   railway run python -m scripts.db_reset
   railway run python -m scripts.insert_sample_docs
   ```
5. Check `https://<your-service>.up.railway.app/health`, then open `/` for the
   widget.

### Embedding the widget on teep.africa

`frontend/widget.js` is the embeddable build: a floating launcher and chat panel
that mount into any page from a single tag.

```html
<script src="https://teep-production.up.railway.app/widget.js" defer></script>
```

teep.africa is a React SPA on Netlify, so add it either in the site repo's
`index.html` before `</body>`, or without touching the repo under
**Site configuration → Build & deploy → Post processing → Snippet injection**,
inserting before `</body>`.

The widget reads the API origin from its own `src`, so the URL is written once.
Everything renders in a shadow root, which keeps the site's Tailwind resets and
the widget's styles from reaching each other.

Optional attributes: `data-api-base` (when the API is not where the script is
served from), `data-brand`, `data-accent`, `data-title`, `data-subtitle`,
`data-greeting`, `data-timeout`. The page can also open the panel from its own
CTA with `window.TeepChat.open()`.

`https://teep.africa` and `https://www.teep.africa` are already in the default
`ALLOWED_ORIGINS`. Netlify deploy previews (`*.netlify.app`) are not — add the
preview URL to that variable if you want to test the widget there first.

Preview it locally at `/embed-preview.html` while `uvicorn` is running.

#### Why the widget never uses a relative path

teep.africa has a SPA catch-all: an unknown path returns `200` with the
marketing page's HTML. A relative `/api/chat` from that domain would therefore
"succeed" with HTML while monitoring saw a `200`. The widget defends against
this twice - it always calls an absolute origin, and it rejects any reply whose
`Content-Type` is not JSON rather than treating the page shell as an answer.

## Rate limiting

`POST /api/chat` is public through the widget and every allowed call spends an
embedding plus a completion, so `app/rate_limit.py` caps each caller at
6 requests a minute and 40 an hour by default. Over either limit the endpoint
returns `429` with a `Retry-After` header and a plain-string `detail` that the
widget shows to the customer as written.

Four things worth knowing:

- **Counters live in Postgres, in `rate_limit_hits`.** An in-process limiter
  was tried first and did not hold: this service runs more than one replica,
  the load balancer round-robins between them, and each kept its own tally.
  Measured against a 6/minute limit, 24 requests let 13 through, with allowed
  and rejected calls interleaved by whichever replica answered. Shared state is
  what makes the configured number the real number. The table is created at
  startup, so a deploy needs no migration step.
- **Callers are identified from `X-Forwarded-For`, reading right to left.**
  `request.client.host` is Railway's proxy and is the same for everyone, so
  limiting on it would throttle all users as one. Within the header, the
  rightmost entry is the one our nearest trusted proxy appended; entries to its
  left came from the caller and can be forged. Taking the leftmost value — the
  usual mistake — would hand out a fresh allowance per forged header. Confirmed
  against the deployed service: forging the header earns no new allowance.
- **The limiter runs before request validation**, so a malformed body still
  counts against the allowance and cannot be used to hammer the endpoint for
  free. It also runs before retrieval, so rejected calls cost nothing.
- **It fails closed.** If the counter query cannot reach Postgres the endpoint
  returns `503` rather than waving the request through. Retrieval needs the
  same database, so failing open would not have kept the bot working — it
  would only have uncapped spend at the worst moment.

Counting costs one extra round trip to Postgres per request, on top of the one
retrieval already makes. Within Railway that is a fraction of a millisecond
against the second or more spent in OpenAI. Run the app from your laptop
against the public proxy, though, and each hit costs about a second.

## Before exposing this publicly

`POST /api/chat` still has no authentication, and the per-IP limits above are
the only ceiling on spend. A distributed caller with many source addresses is
not covered; add a global cap if that becomes a concern.
