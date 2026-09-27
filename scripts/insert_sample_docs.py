"""
Seed the `documents` table from the TEEP knowledge base markdown.

Usage:
    python -m scripts.insert_sample_docs [path/to/knowledge_base.md] [--append]

Chunking is section-aware: one chunk per `##` heading, with the heading kept at
the top of the chunk's content. Splitting on blank lines instead (the old
behaviour) stripped headings into chunks of their own, so a row like "## Refund
Policy" carried no answer, and the paragraph below it lost the only clue that it
was about refunds.

By default a run replaces whatever is already in `documents`, because re-seeding
an updated knowledge base should not leave the previous version's rows behind to
compete for the top_k slots. Pass --append to keep the existing rows.
"""
import os
import re
import sys

from sqlalchemy import create_engine, text

from app.config import settings
from app.services.embedding_service import generate_embeddings, to_vector_literal

DEFAULT_KB = os.path.join("data", "teep_knowledge_base.md")

# ada-002 handles ~8k tokens per input; sections well under that still embed
# better when they are about one thing, so split the long ones on paragraphs.
MAX_CHARS_PER_CHUNK = 2000


def _split_long_section(heading: str, body: str) -> list:
    """Split an oversized section into paragraph-aligned chunks, heading intact."""
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    chunks, current = [], []

    for para in paragraphs:
        candidate = current + [para]
        if current and len(heading) + 2 + len("\n\n".join(candidate)) > MAX_CHARS_PER_CHUNK:
            chunks.append("\n\n".join(current))
            current = [para]
        else:
            current = candidate
    if current:
        chunks.append("\n\n".join(current))

    return chunks


def build_chunks(markdown: str) -> list:
    """
    Turn the knowledge base into [(title, content), ...].

    `title` is the section heading, `content` is the heading plus its body, so
    the embedded text and the text handed to the LLM both say what the section
    is about.
    """
    # Drop the `# Title` preamble; it is a label, not an answer to anything.
    sections = re.split(r"^## ", markdown, flags=re.MULTILINE)[1:]
    chunks = []

    for section in sections:
        heading, _, body = section.partition("\n")
        heading, body = heading.strip(), body.strip()
        if not body:
            continue

        for piece in _split_long_section(heading, body):
            chunks.append((heading, f"{heading}\n\n{piece}"))

    return chunks


def insert_sample_docs(kb_path: str = DEFAULT_KB, append: bool = False) -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.normpath(os.path.join(project_root, kb_path))

    with open(data_path, "r", encoding="utf-8") as f:
        markdown = f.read()

    chunks = build_chunks(markdown)
    if not chunks:
        raise SystemExit(f"No sections found in {data_path} - expected '## ' headings")
    print(f"{os.path.basename(data_path)}: {len(chunks)} chunks to embed")

    # One request for the whole batch instead of one per chunk.
    embeddings = generate_embeddings([content for _, content in chunks])

    engine = create_engine(settings.DATABASE_URL, echo=False)
    with engine.connect() as conn:
        if not append:
            removed = conn.execute(text("DELETE FROM documents")).rowcount
            print(f"Cleared {removed} existing rows from documents")

        insert_sql = text("""
            INSERT INTO documents (title, content, embedding)
            VALUES (:title, :content, CAST(:embedding AS vector))
        """)
        for (title, content), embedding in zip(chunks, embeddings):
            conn.execute(insert_sql, {
                "title": title[:255],
                "content": content,
                "embedding": to_vector_literal(embedding),
            })
        conn.commit()
        print(f"Inserted {len(chunks)} documents")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--append"]
    insert_sample_docs(
        kb_path=args[0] if args else DEFAULT_KB,
        append="--append" in sys.argv[1:],
    )
