"""
Integration Ingestion Script
=============================
Loops through ALL .txt files in /data/, parses them into structured chunks
with metadata (document_name, article_number, paragraph_number, department),
and ingests them into the local Qdrant instance.

Department assignment:
    - Files with 'fiod' in the filename → department='FIOD'
    - All other files → department='Tax Policy'

Prerequisites:
    1. Qdrant must be running: docker compose up -d
    2. pip install -r requirements.txt
"""
import os
import re
import glob
from dotenv import load_dotenv
from llama_index.core import Document

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def detect_department(filename):
    """
    Assigns department based on filename.
    Files containing 'fiod' (case-insensitive) are classified as FIOD.
    """
    if "fiod" in filename.lower():
        return "FIOD"
    return "Tax Policy"


def parse_tax_document(filepath):
    """
    Parses a structured tax document into LlamaIndex Documents
    with per-paragraph metadata for strict citation support.
    Overrides the department field based on filename.
    """
    filename = os.path.basename(filepath)
    department = detect_department(filename)

    with open(filepath, "r") as f:
        raw_text = f.read()

    # Extract document-level metadata from the header
    doc_name_match = re.search(r"DOCUMENT:\s*(.+)", raw_text)
    classification_match = re.search(r"CLASSIFICATION:\s*(.+)", raw_text)

    doc_name = doc_name_match.group(1).strip() if doc_name_match else filename
    classification = classification_match.group(1).strip() if classification_match else "Public"

    # Split into articles
    articles = re.split(r"---\s*ARTICLE\s+(\d+)\s*---", raw_text)

    documents = []
    # articles[0] is the header, then pairs of (article_number, article_body)
    for i in range(1, len(articles), 2):
        article_number = articles[i].strip()
        article_body = articles[i + 1].strip() if i + 1 < len(articles) else ""

        # Split each article into paragraphs
        paragraphs = re.findall(r"Paragraph\s+(\d+):\s*(.+)", article_body)

        for para_num, para_text in paragraphs:
            metadata = {
                "document_name": doc_name,
                "article_number": f"Article {article_number}",
                "paragraph_number": f"Paragraph {para_num}",
                "classification": classification,
                "department": department,
                "security_clearance": classification,  # For RBAC filtering
            }
            documents.append(
                Document(text=para_text.strip(), metadata=metadata)
            )

    return documents


def main():
    print("=" * 60)
    print("  Tax Authority RAG — Integration Ingestion")
    print("=" * 60)

    # 1. Discover all .txt files in /data/
    txt_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.txt")))
    print(f"\n[1/3] Found {len(txt_files)} files in {DATA_DIR}/")

    if not txt_files:
        print("      ❌ No .txt files found. Generate data first: python generate_data.py")
        return

    # 2. Parse all files
    all_documents = []
    for filepath in txt_files:
        filename = os.path.basename(filepath)
        department = detect_department(filename)
        docs = parse_tax_document(filepath)
        all_documents.extend(docs)
        print(f"      📄 {filename:<45} → dept={department:<12} | {len(docs):>5} paragraphs")

    print(f"\n      Total: {len(all_documents)} paragraphs across {len(txt_files)} files")

    # Count FIOD vs non-FIOD
    fiod_count = sum(1 for d in all_documents if d.metadata["department"] == "FIOD")
    non_fiod_count = len(all_documents) - fiod_count
    print(f"      FIOD documents:     {fiod_count}")
    print(f"      Non-FIOD documents: {non_fiod_count}")

    # 3. Ingest into Qdrant via modules/ingestion.py
    print(f"\n[2/3] Ingesting {len(all_documents)} chunks into Qdrant (localhost:6333)...")
    try:
        from modules.ingestion import ingest_data
        index = ingest_data(all_documents)
        print(f"      ✅ Successfully indexed {len(all_documents)} chunks into Qdrant.")
    except Exception as e:
        print(f"      ❌ Qdrant ingestion failed: {e}")
        print(f"      💡 Make sure Qdrant is running: docker compose up -d")
        return

    # 4. Quick sanity query
    print(f"\n[3/3] Running sanity query...")
    try:
        query_engine = index.as_query_engine()
        response = query_engine.query("What is the corporate tax rate for 2024?")
        print(f"      Query:    'What is the corporate tax rate for 2024?'")
        print(f"      Response: {response}")
    except Exception as e:
        print(f"      ⚠️  Query test skipped (expected without LLM configured): {e}")

    print("\n" + "=" * 60)
    print("  Ingestion complete. You can now run: python main.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
