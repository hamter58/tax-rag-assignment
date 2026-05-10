from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
import qdrant_client
from dotenv import load_dotenv

load_dotenv()

# Define the LangGraph State
class GraphState(TypedDict):
    question: str
    generation: str
    documents: List[Dict]  # Each document is a dict with 'text' and 'metadata' keys
    relevance_score: str

# LLM Node Implementations
def call_gemini_grader(question: str, document: Dict) -> str:
    """
    Uses 'gemini-3-flash' for the Grader node to check document relevance.
    """
    # Mocking the call to gemini-3-flash
    return "yes"

def call_claude_generator(question: str, documents: List[Dict]) -> str:
    """
    Uses 'claude-sonnet-4.6-thinking' for the Generator node to format
    the final answer with exact citations.

    STRICT CITATION RULES:
    The model MUST read the following fields from each chunk's metadata:
        - metadata["document_name"]
        - metadata["article_number"]
        - metadata["paragraph_number"]

    Every claim in the output MUST end with a citation in exactly this format:
        [Document Name, Article X, Paragraph Y]

    Example:
        "The corporate tax rate is 25.8% [Wet Vpb 2024, Article 22, Paragraph 1]."
    """
    # Mocking the call to claude-sonnet-4.6-thinking
    citations = []
    for doc in documents:
        meta = doc.get("metadata", {})
        doc_name = meta.get("document_name", "Unknown")
        article = meta.get("article_number", "Unknown")
        paragraph = meta.get("paragraph_number", "Unknown")
        citations.append(f"[{doc_name}, {article}, {paragraph}]")

    citation_str = " ".join(citations)
    return f"Based on the documents provided, here is the answer: ... {citation_str}"

# Node Functions
def retrieve_node(state: GraphState):
    """
    Real retrieval node: queries Qdrant with RBAC pre-filtering.
    User role is 'Helpdesk' — FIOD documents are blocked at the DB level.
    """
    print("---RETRIEVE---")
    question = state["question"]

    # 1. Build RBAC filter — Helpdesk users cannot see FIOD documents
    from modules.security import get_rbac_filter
    rbac_filter = get_rbac_filter(user_role="Helpdesk", user_department="Helpdesk")
    print(f"      RBAC filter applied: role=Helpdesk, FIOD documents blocked")

    # 2. Query Qdrant directly with the RBAC filter
    from modules.ingestion import Settings
    client = qdrant_client.QdrantClient(url="localhost", port=6333)
    collection_name = "tax_authority_docs"

    # Embed the question using the same Gemini model used for ingestion
    embed_model = Settings.embed_model
    query_embedding = embed_model.get_query_embedding(question)

    # 3. Execute filtered vector search against Qdrant
    search_results = client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        query_filter=rbac_filter,
        limit=5,
        with_payload=True,
    )

    # 4. Convert Qdrant results to our GraphState document format
    documents = []
    for point in search_results.points:
        payload = point.payload or {}
        # LlamaIndex stores text in '_node_content' or 'text'; metadata fields are top-level
        text = payload.get("text", payload.get("_node_content", ""))
        doc = {
            "text": text,
            "metadata": {
                "document_name": payload.get("document_name", "Unknown"),
                "article_number": payload.get("article_number", "Unknown"),
                "paragraph_number": payload.get("paragraph_number", "Unknown"),
                "department": payload.get("department", "Unknown"),
                "classification": payload.get("classification", "Unknown"),
            }
        }
        documents.append(doc)
        print(f"      Retrieved: {doc['metadata']['document_name']} | "
              f"{doc['metadata']['article_number']}, {doc['metadata']['paragraph_number']} | "
              f"dept={doc['metadata']['department']} | score={point.score:.4f}")

    if not documents:
        print("      ⚠️  No documents retrieved from Qdrant.")

    return {"documents": documents, "question": question}

def grade_documents_node(state: GraphState):
    print("---GRADE DOCUMENTS (gemini-3-flash)---")
    question = state["question"]
    documents = state["documents"]

    filtered_docs = []
    for doc in documents:
        score = call_gemini_grader(question, doc)
        if score == "yes":
            filtered_docs.append(doc)

    return {"documents": filtered_docs, "question": question}

def generate_node(state: GraphState):
    print("---GENERATE (claude-sonnet-4.6-thinking)---")
    question = state["question"]
    documents = state["documents"]

    generation = call_claude_generator(question, documents)
    return {"documents": documents, "question": question, "generation": generation}

def fallback_action_node(state: GraphState):
    """
    Strict fallback: No rewrite loops allowed.
    If the Grader rejected all documents, the system must refuse to answer
    rather than risk hallucinating tax advice.
    """
    print("---FALLBACK ACTION---")
    return {
        "question": state["question"],
        "documents": state["documents"],
        "generation": "I'm sorry, I cannot find sufficient legal context in the tax corpus to answer this question accurately."
    }

# Conditional Logic (Corrective RAG)
def decide_to_generate(state: GraphState):
    print("---DECIDE TO GENERATE---")
    filtered_docs = state["documents"]

    if not filtered_docs:
        # No relevant documents survived the Grader — route to fallback, do NOT rewrite.
        return "fallback"
    else:
        return "generate"

def build_crag_graph():
    """
    Builds the LangGraph state machine for Corrective RAG (CRAG).
    """
    workflow = StateGraph(GraphState)

    # Add Nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade_documents", grade_documents_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("fallback_action", fallback_action_node)

    # Build Graph Edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade_documents")

    workflow.add_conditional_edges(
        "grade_documents",
        decide_to_generate,
        {
            "fallback": "fallback_action",
            "generate": "generate",
        }
    )
    # Both terminal nodes end the graph — no infinite loops
    workflow.add_edge("fallback_action", END)
    workflow.add_edge("generate", END)

    return workflow.compile()

if __name__ == "__main__":
    app = build_crag_graph()

    inputs = {"question": "What is the new tax regulation for 2026?"}
    for output in app.stream(inputs):
        for key, value in output.items():
            print(f"Node '{key}': {value}")
        print("---")
