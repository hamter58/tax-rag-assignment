import os
import time
import qdrant_client
from dotenv import load_dotenv
from qdrant_client.http.models import Distance, VectorParams, HnswConfigDiff, ScalarQuantization, ScalarQuantizationConfig, ScalarType
from llama_index.core import Document, Settings
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import StorageContext
from llama_index.embeddings.gemini import GeminiEmbedding

# Load API keys from .env
load_dotenv()

# Configure LlamaIndex to use Google Gemini embeddings (3072-dim) instead of OpenAI
# embed_batch_size=10 to minimize per-request token load and avoid 429 rate-limit errors
Settings.embed_model = GeminiEmbedding(
    model_name="models/gemini-embedding-001",
    api_key=os.getenv("GOOGLE_API_KEY"),
    embed_batch_size=10,
)

def setup_qdrant_client(url="localhost", port=6333):
    """
    Initializes Qdrant client with HNSW and Scalar Quantization.
    """
    client = qdrant_client.QdrantClient(url=url, port=port)
    
    collection_name = "tax_authority_docs"
    
    # Configure Qdrant with HNSW (m=32, ef_construct=200) and Scalar Quantization
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=3072, # gemini-embedding-001 output dimension
            distance=Distance.COSINE
        ),
        hnsw_config=HnswConfigDiff(
            m=32,
            ef_construct=200
        ),
      quantization_config=ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                always_ram=True
            )
        )
    )
    return client, collection_name

def process_documents_hierarchical(documents):
    """
    Hierarchical Chunking tracking Document, Article, Paragraph.
    """
    # Chunk sizes set to represent Document -> Article -> Paragraph levels
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[2048, 512, 128],
        chunk_overlap=20
    )
    
    nodes = node_parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes)
    
    # Ensure metadata is explicitly attached to the leaf nodes for strict citations
    for node in leaf_nodes:
        # In a real scenario, these would be extracted via Regex or a MetadataExtractor
        node.metadata["document_name"] = "Tax_Code_2024.pdf" 
        node.metadata["article_number"] = "Extracted_Article_X"
        node.metadata["paragraph_number"] = "Extracted_Paragraph_Y"
        node.metadata["security_clearance"] = "Public" # For RBAC filtering
    
    return nodes, leaf_nodes

def _embed_batch_with_retry(index, batch, is_first, storage_context, max_retries=5, initial_wait=30):
    """
    Embeds a single batch with exponential backoff retry on 429 errors.
    """
    for attempt in range(1, max_retries + 1):
        try:
            if is_first:
                from llama_index.core import VectorStoreIndex
                index = VectorStoreIndex(
                    batch,
                    storage_context=storage_context,
                    embed_model=Settings.embed_model,
                    show_progress=True,
                )
            else:
                index.insert_nodes(batch)
            return index  # Success
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Resource exhausted" in error_str:
                wait_time = initial_wait * (2 ** (attempt - 1))  # 30s, 60s, 120s, 240s, 480s
                print(f"      ⚠️  Rate limited (attempt {attempt}/{max_retries}). "
                      f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                raise  # Non-rate-limit error, propagate immediately

    raise RuntimeError(f"Failed after {max_retries} retries due to persistent rate limiting.")

def ingest_data(documents, batch_size=100, sleep_seconds=2):
    client, collection_name = setup_qdrant_client()
    vector_store = QdrantVectorStore(client=client, collection_name=collection_name)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    nodes, leaf_nodes = process_documents_hierarchical(documents)
    
    # Batched ingestion with exponential backoff to respect Google API rate limits
    total = len(leaf_nodes)
    num_batches = (total + batch_size - 1) // batch_size
    index = None

    for i in range(0, total, batch_size):
        batch = leaf_nodes[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        print(f"      ⏳ Batch {batch_num}/{num_batches}: embedding nodes {i+1}-{min(i+batch_size, total)} of {total}")

        is_first = (index is None)
        index = _embed_batch_with_retry(index, batch, is_first, storage_context)

        # Sleep between batches to respect rate limits (skip after the last batch)
        if i + batch_size < total:
            print(f"      💤 Sleeping {sleep_seconds}s to respect API rate limits...")
            time.sleep(sleep_seconds)

    return index

