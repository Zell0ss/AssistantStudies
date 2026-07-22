# modules/memory.py
"""
Memory module - episodic memory over Qdrant, embeddings via OpenAI.

Enhancement, not critical path: OpenAI/Qdrant failures never raise — store()
and search() catch their own errors and return {'success': False, ...} so a
memory outage never breaks the orchestrator turn.
"""
import uuid
from datetime import datetime, timezone

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from logcentral_client import get_logger

logger = get_logger("sebastian")

_EMBEDDING_MODEL = "text-embedding-3-small"


class MemoryModule:

    def __init__(self, collection_name, openai_api_key, qdrant_url="http://localhost:6333"):
        self._collection = collection_name
        self._openai = OpenAI(api_key=openai_api_key)
        self._qdrant = QdrantClient(url=qdrant_url)

    def embed(self, text):
        """Return the text-embedding-3-small vector for `text`. Raises on failure —
        callers (store/search) are responsible for catching and degrading gracefully."""
        response = self._openai.embeddings.create(model=_EMBEDDING_MODEL, input=text)
        return response.data[0].embedding

    def store(self, content, tags=None):
        """
        Embed and persist `content` as a memory point.

        Returns:
            {'success': True, 'result': str, 'data': {'id': str}}
            | {'success': False, 'result': str, 'data': {}}
        """
        try:
            vector = self.embed(content)
        except Exception as e:
            logger.warning(f"MemoryModule.store: embedding failed: {e}")
            return {'success': False, 'result': "No pude generar el embedding para guardar esto en memoria.", 'data': {}}

        point_id = str(uuid.uuid4())
        payload = {
            'content': content,
            'tags': tags or [],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'conversation',
        }
        try:
            self._qdrant.upsert(
                collection_name=self._collection,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )
        except Exception as e:
            logger.warning(f"MemoryModule.store: qdrant upsert failed: {e}")
            return {'success': False, 'result': "No pude guardar esto en memoria ahora mismo.", 'data': {}}

        logger.info(f"Stored memory {point_id}: {content[:80]}")
        return {'success': True, 'result': "Guardado en memoria.", 'data': {'id': point_id}}

    def search(self, query, k=5):
        """
        Search for memories semantically related to `query`.

        Returns:
            {'success': True, 'result': str, 'data': {'matches': [{'content', 'tags', 'score'}, ...]}}
            | {'success': False, 'result': str, 'data': {}}
        """
        try:
            vector = self.embed(query)
        except Exception as e:
            logger.warning(f"MemoryModule.search: embedding failed: {e}")
            return {'success': False, 'result': "No pude generar el embedding para buscar en memoria.", 'data': {}}

        try:
            hits = self._qdrant.query_points(
                collection_name=self._collection,
                query=vector,
                limit=k,
            ).points
        except Exception as e:
            logger.warning(f"MemoryModule.search: qdrant search failed: {e}")
            return {'success': False, 'result': "No pude acceder a la memoria ahora mismo.", 'data': {}}

        matches = [
            {'content': h.payload.get('content'), 'tags': h.payload.get('tags', []), 'score': h.score}
            for h in hits
        ]
        logger.info(f"Memory search '{query[:60]}' -> {len(matches)} matches")
        return {'success': True, 'result': f"{len(matches)} resultado(s) encontrado(s).", 'data': {'matches': matches}}
