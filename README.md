# Tax Authority Enterprise RAG

An enterprise-grade Retrieval-Augmented Generation (RAG) orchestration system designed for the Dutch National Tax Authority. This pipeline processes massive tax corpora, enforces strict legal citations, prevents hallucinations, and mathematically guarantees security through pre-retrieval Role-Based Access Control (RBAC).

## 🌟 Key Features

1. **Hierarchical Chunking**: Preserves structural metadata (`Document` → `Article` → `Paragraph`) for highly accurate legal context extraction.
2. **Pre-Retrieval RBAC Security**: Hard-filters classified documents (e.g., FIOD investigations) directly at the Vector DB layer, ensuring unauthorized roles (like 'Helpdesk') never even retrieve sensitive data.
3. **Corrective RAG (CRAG) Pipeline**: Powered by LangGraph, featuring a strict Compliance Grader that forces a deterministic fallback ("I cannot answer this") if the retrieved context is insufficient, enforcing a zero-hallucination policy.
4. **Hybrid Search & Reranking**: Combines dense vector search (Google Gemini embeddings) with sparse keyword search (BM25), fused via Reciprocal Rank Fusion (RRF), and re-ranked using a multilingual Cross-Encoder (`bge-reranker-v2-m3`).
5. **Semantic Caching**: Utilizes Redis Vector Search to cache and return exact matches for identical queries, featuring an ultra-strict cosine similarity threshold (0.98) to prevent conflating nuanced tax years (e.g., 2024 vs 2025).
6. **Resilient Ingestion Pipeline**: Handles massive document ingestion with built-in batching, token rate-limiting mitigation, and exponential backoff.

## 🛠️ Technology Stack

* **Orchestration**: LangGraph, LlamaIndex
* **Vector Database**: Qdrant (Local Docker)
* **Semantic Cache**: Redis Stack (RediSearch)
* **Embeddings**: Google Gemini (`gemini-embedding-001` - 3072 dim)
* **LLMs**: Google Gemini 1.5 Flash (Grader), Anthropic Claude 3.5 Sonnet (Generator)
* **Retrieval**: Sentence-Transformers, Rank-BM25

---

## 🚀 How to Start

### 1. Prerequisites
* Python 3.9+
* Docker Desktop (for Qdrant and Redis)

### 2. Setup Environment
```bash
# Clone the repository
git clone https://github.com/hamter58/tax-rag-assignment.git
cd tax-rag-assignment

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Keys
Create a `.env` file in the root directory and add your keys:
```env
GOOGLE_API_KEY="your_gemini_api_key_here"
ANTHROPIC_API_KEY="your_claude_api_key_here"
```

### 4. Start Infrastructure
Spin up Qdrant and Redis locally using Docker:
```bash
docker compose up -d
```

### 5. Generate & Ingest Data
Generate the synthetic tax regulations and ingest them into the Qdrant database:
```bash
# Generates 10+ massive hierarchical tax documents in /data/
python generate_data.py

# Parses, embeds, and ingests the data into Qdrant (with rate-limit handling)
python ingest_test.py
```

### 6. Run the Application
Execute the full CRAG pipeline. The default script runs as a 'Helpdesk' user to demonstrate the RBAC filtering in action.
```bash
python main.py
```

---

## 🤖 How AI Was Used to Build This

This project was co-developed using an **Agentic AI Coding Assistant** (Google DeepMind's Antigravity). The AI was utilized to simulate an enterprise engineering team through specialized personas:

1. **AI Architect Persona**: Designed the high-level architecture, selecting the exact chunking strategies, vector dimension sizes, reranker models, and deciding where security layers (RBAC) should sit mathematically in the database layer.
2. **AI Developer Persona**: Generated the production-ready Python implementations. The AI actively debugged complex rate-limiting issues from the Google API, implementing an elegant exponential backoff retry loop during data ingestion.
3. **Prompt Engineering**: The AI drafted the strict Markdown files (`prompts/` and `agent_personas/`) that govern the sub-agents (e.g., forcing the Generator to use explicit metadata arrays for its citations).
4. **Synthetic Data Generation**: LLMs were used to instantly generate thousands of paragraphs of cohesive, legally structured mock data (Tax Treaties, FIOD Audit Reports) to simulate the volume and complexity of a real Tax Authority corpus.
