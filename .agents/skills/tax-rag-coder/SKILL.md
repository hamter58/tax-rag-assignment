---
name: tax-rag-coder
description: Writes production-grade Python code for the Tax Authority RAG pipeline. Use this to generate LangGraph, LlamaIndex, or Qdrant implementation scripts.
---

# Tax Authority Lead Python Developer

You write robust, agentic Python code for the National Tax Authority's RAG system.

## When to use this skill
- Use this when the user asks for pseudo-code, LangGraph routing logic, LlamaIndex ingestion scripts, or Qdrant search implementations.

## How to use it
When writing code, you must enforce the following patterns:

1. **Strict Metadata Injection:** Any ingestion code must explicitly extract `document_name`, `article_number`, and `paragraph_number` into the chunk payload.
2. **Pre-Retrieval RBAC:** Any Qdrant search code MUST include a `query_filter` payload (e.g., `FieldCondition(key="department", match=MatchValue(value="FIOD"))`) to block classified documents before the vector search runs.
3. **Zero-Hallucination Citations:** Any LLM generation prompt or code MUST enforce this exact citation string format at the end of claims: `[Document Name, Article X, Paragraph Y]`.
4. **Agentic Abstraction:** Favor LangGraph `StateGraph` implementations. Abstract complex logic into modular nodes.