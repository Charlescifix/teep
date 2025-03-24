import os
from sqlalchemy import create_engine, text
from app.config import settings
from app.services.embedding_service import generate_embedding

def insert_sample_docs():
    engine = create_engine(settings.DATABASE_URL, echo=True)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Build an absolute path to sample_documents.md
    data_path = os.path.join(script_dir, "..", "data", "sample_documents.md")
    data_path = os.path.normpath(data_path)

    with open(data_path, "r", encoding="utf-8") as f:
        file_contents = f.read()

    # Example: split by headings or blank lines
    # This is just one possible approach. Adjust as needed.
    # Splitting by triple-dashes or blank lines is also common.
    chunks = file_contents.split("\n\n")

    with engine.connect() as conn:
        insert_sql = text("""
            INSERT INTO documents (title, content, embedding)
            VALUES (:title, :content, :embedding)
        """)

        # Insert each chunk as a separate row
        for i, chunk in enumerate(chunks, start=1):
            chunk_text = chunk.strip()
            if not chunk_text:
                continue  # skip empty lines

            # Generate embedding for this chunk
            embed = generate_embedding(chunk_text)

            # Insert into DB
            conn.execute(insert_sql, {
                "title": f"TEEP Overview Part {i}",
                "content": chunk_text,
                "embedding": embed
            })
        conn.commit()

if __name__ == "__main__":
    insert_sample_docs()
