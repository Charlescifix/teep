import os
from sqlalchemy import create_engine, text
from app.config import settings
from app.services.embedding_service import generate_embedding, to_vector_literal

def is_meaningful(chunk: str) -> bool:
    """
    True if a chunk carries actual content worth embedding.

    Splitting on blank lines also yields the markdown horizontal rules ("---")
    that separate sections. Those are noise: they cost an embedding call each
    and, once stored, compete for the top_k slots that retrieval hands to the
    LLM, pushing real answers out of the context.
    """
    return any(c.isalnum() for c in chunk)


def insert_sample_docs():
    engine = create_engine(settings.DATABASE_URL, echo=False)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Build an absolute path to sample_documents.md
    data_path = os.path.join(script_dir, "..", "data", "sample_documents.md")
    data_path = os.path.normpath(data_path)

    with open(data_path, "r", encoding="utf-8") as f:
        file_contents = f.read()

    # Split on blank lines, then drop separators and whitespace-only fragments
    # up front so the "Part N" numbering below stays contiguous.
    chunks = [c.strip() for c in file_contents.split("\n\n")]
    chunks = [c for c in chunks if is_meaningful(c)]
    print(f"{len(chunks)} chunks to embed")

    with engine.connect() as conn:
        insert_sql = text("""
            INSERT INTO documents (title, content, embedding)
            VALUES (:title, :content, CAST(:embedding AS vector))
        """)

        # Insert each chunk as a separate row
        for i, chunk_text in enumerate(chunks, start=1):
            # Generate embedding for this chunk
            embed = generate_embedding(chunk_text)

            # Insert into DB
            conn.execute(insert_sql, {
                "title": f"TEEP Overview Part {i}",
                "content": chunk_text,
                "embedding": to_vector_literal(embed)
            })
        conn.commit()
        print(f"Inserted {len(chunks)} documents")

if __name__ == "__main__":
    insert_sample_docs()
