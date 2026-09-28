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

## Before exposing this publicly

`POST /api/chat` has no authentication or rate limiting, and every call spends
OpenAI credits on one embedding plus one completion.
