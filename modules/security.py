from qdrant_client.http import models
import numpy as np
import json
import uuid

def get_rbac_filter(user_role, user_department):
    """
    DB-level Metadata Pre-filtering (RBAC).
    Blocks FIOD documents for unauthorized users.
    """
    must_conditions = []
    must_not_conditions = []
    
    # Block FIOD documents unless the user department is explicitly 'FIOD'
    if user_department != "FIOD":
        must_not_conditions.append(
            models.FieldCondition(
                key="department",
                match=models.MatchValue(value="FIOD")
            )
        )
    
    # Additional DB-level Metadata checks can be added here based on role
    if user_role == "public":
        must_conditions.append(
            models.FieldCondition(
                key="classification",
                match=models.MatchValue(value="public")
            )
        )
        
    return models.Filter(
        must=must_conditions if must_conditions else None,
        must_not=must_not_conditions if must_not_conditions else None
    )

class RedisSemanticCache:
    """
    True Semantic Cache using Redis Vector Search (RediSearch).
    Stores query embeddings and uses cosine similarity to find
    semantically equivalent previously-cached queries.

    Redis Search imports are lazy-loaded so that importing security.py
    for RBAC (get_rbac_filter) doesn't crash when Redis isn't available.
    """

    INDEX_NAME = "idx:semantic_cache"
    DOC_PREFIX = "cache:"

    def __init__(self, host='localhost', port=6379, vector_dim=768, ttl_seconds=3600):
        import redis
        from redis.commands.search.field import VectorField, TextField
        try:
            from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        except ModuleNotFoundError:
            # redis >= 7.x renamed the module
            from redis.commands.search.index_definition import IndexDefinition, IndexType

        self.redis_client = redis.Redis(host=host, port=port, decode_responses=False)
        self.vector_dim = vector_dim
        self.ttl_seconds = ttl_seconds

        # Because this is financial/tax data, the cosine similarity threshold is
        # strictly set to 0.98 to prevent false-positive cache matches on nuanced
        # tax questions (e.g., "Article 12 Paragraph 3 for 2024" vs "Article 12
        # Paragraph 3 for 2025" are semantically close but legally distinct).
        self.cosine_similarity_threshold = 0.98

        # Store classes for use in _create_index
        self._VectorField = VectorField
        self._TextField = TextField
        self._IndexDefinition = IndexDefinition
        self._IndexType = IndexType

        self._create_index()

    def _create_index(self):
        """Creates the RediSearch vector index if it does not already exist."""
        try:
            self.redis_client.ft(self.INDEX_NAME).info()
        except Exception:
            schema = (
                self._TextField("$.query_text", as_name="query_text"),
                self._TextField("$.result", as_name="result"),
                self._VectorField(
                    "$.query_embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dim,
                        "DISTANCE_METRIC": "COSINE",
                    },
                    as_name="query_embedding",
                ),
            )
            definition = self._IndexDefinition(
                prefix=[self.DOC_PREFIX], index_type=self._IndexType.JSON
            )
            self.redis_client.ft(self.INDEX_NAME).create_index(
                fields=schema, definition=definition
            )

    def get(self, query_text, query_embedding):
        """
        Searches the cache for a semantically similar query using vector search.
        Returns the cached result only if similarity >= self.cosine_similarity_threshold.

        Args:
            query_text: The raw query string (for logging/debugging).
            query_embedding: The query's embedding vector (list or np.ndarray).
        
        Returns:
            The cached result dict if a semantic match is found, otherwise None.
        """
        from redis.commands.search.query import Query

        embedding_bytes = np.array(query_embedding, dtype=np.float32).tobytes()

        # KNN vector search: find the single nearest cached query embedding
        q = (
            Query("(*)=>[KNN 1 @query_embedding $vec AS score]")
            .sort_by("score")
            .return_fields("score", "query_text", "result")
            .dialect(2)
        )

        results = self.redis_client.ft(self.INDEX_NAME).search(
            q, query_params={"vec": embedding_bytes}
        )

        if results.total == 0:
            return None

        top_hit = results.docs[0]
        # Redis COSINE distance = 1 - cosine_similarity
        cosine_similarity = 1 - float(top_hit.score)

        if cosine_similarity >= self.cosine_similarity_threshold:
            return json.loads(top_hit.result)

        return None

    def set(self, query_text, query_embedding, result):
        """
        Stores a query embedding and its result in the semantic cache.

        Args:
            query_text: The raw query string.
            query_embedding: The query's embedding vector (list or np.ndarray).
            result: The result dict to cache.
        """
        key = f"{self.DOC_PREFIX}{uuid.uuid4().hex}"
        embedding_list = np.array(query_embedding, dtype=np.float32).tolist()

        payload = {
            "query_text": query_text,
            "query_embedding": embedding_list,
            "result": json.dumps(result),
        }

        self.redis_client.json().set(key, "$", payload)
        self.redis_client.expire(key, self.ttl_seconds)

