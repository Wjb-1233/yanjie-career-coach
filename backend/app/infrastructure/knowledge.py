import hashlib
import math
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass(slots=True)
class KnowledgeDocument:
    id: str
    title: str
    content: str
    category: str


class KnowledgeStore:
    def __init__(self) -> None:
        self._documents: dict[str, KnowledgeDocument] = {}
        self._remote_available = False
        self._initialized = False

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * settings.milvus_dimension
        normalized = "".join(text.lower().split())
        for index in range(len(normalized)):
            token = normalized[index : index + 2]
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            bucket = int.from_bytes(digest[:8], "big") % len(values)
            values[bucket] += 1.0 if digest[8] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    async def upsert(self, documents: list[KnowledgeDocument]) -> None:
        self._documents.update({document.id: document for document in documents})
        if not settings.milvus_enabled:
            return
        try:
            await self._ensure_collection()
            data = [
                {
                    "doc_id": document.id,
                    "title": document.title,
                    "content": document.content,
                    "category": document.category,
                    "vector": self._embed(document.title + document.content),
                }
                for document in documents
            ]
            await self._post(
                "/v2/vectordb/entities/upsert",
                {"collectionName": settings.milvus_collection, "data": data},
            )
            self._remote_available = True
        except Exception:
            self._remote_available = False

    async def search(self, query: str, limit: int = 3) -> list[KnowledgeDocument]:
        if settings.milvus_enabled:
            try:
                payload = await self._post(
                    "/v2/vectordb/entities/search",
                    {
                        "collectionName": settings.milvus_collection,
                        "data": [self._embed(query)],
                        "annsField": "vector",
                        "limit": limit,
                        "outputFields": ["doc_id", "title", "content", "category"],
                        "searchParams": {"metricType": "COSINE", "params": {}},
                    },
                )
                rows = payload.get("data") or []
                if rows:
                    self._remote_available = True
                    return [
                        KnowledgeDocument(
                            id=str(row.get("doc_id", row.get("id"))),
                            title=row.get("title", ""),
                            content=row.get("content", ""),
                            category=row.get("category", ""),
                        )
                        for row in rows
                    ]
            except Exception:
                self._remote_available = False
        query_vector = self._embed(query)

        def score(document: KnowledgeDocument) -> float:
            vector = self._embed(document.title + document.content)
            return sum(left * right for left, right in zip(query_vector, vector, strict=True))

        return sorted(self._documents.values(), key=score, reverse=True)[:limit]

    async def _ensure_collection(self) -> None:
        if self._initialized:
            return
        listed = await self._post("/v2/vectordb/collections/list", {})
        raw_data = listed.get("data", [])
        names = raw_data if isinstance(raw_data, list) else raw_data.get("collectionNames", [])
        if settings.milvus_collection not in names:
            await self._post(
                "/v2/vectordb/collections/create",
                {
                    "collectionName": settings.milvus_collection,
                    "dimension": settings.milvus_dimension,
                    "metricType": "COSINE",
                    "idType": "VarChar",
                    "primaryFieldName": "doc_id",
                    "vectorFieldName": "vector",
                    "autoID": False,
                    "params": {"max_length": 128, "enableDynamicField": True},
                },
            )
        self._initialized = True

    async def _post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient(
            base_url=settings.milvus_uri.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.milvus_token}"},
            timeout=5,
        ) as client:
            response = await client.post(path, json=body)
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") not in (0, 200, None):
            raise RuntimeError(payload.get("message", "Milvus request failed"))
        return payload

    @property
    def mode(self) -> str:
        return "milvus" if self._remote_available else "memory"


knowledge_store = KnowledgeStore()

