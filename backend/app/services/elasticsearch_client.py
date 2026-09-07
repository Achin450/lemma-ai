import logging
import math
import re
import json
from pathlib import Path
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from app.config import settings

logger = logging.getLogger(__name__)

_es_client = None


class InMemoryBM25:
    """High-performance in-memory BM25 lexical matching engine for environments where Elasticsearch is offline or not installed."""
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: list[dict] = []
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.doc_freqs: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.total_docs: int = 0

    def tokenize(self, text: str) -> list[str]:
        return [w.lower() for w in re.findall(r'\b\w+\b', text) if len(w) > 1]

    def add_documents(self, documents: list[dict]) -> None:
        if not documents:
            return
        for doc in documents:
            text = doc.get("text", "")
            tokens = self.tokenize(text)
            self.corpus.append(doc)
            self.doc_len.append(len(tokens))
            for t in set(tokens):
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.total_docs = len(self.corpus)
        if self.total_docs > 0:
            self.avgdl = sum(self.doc_len) / self.total_docs
            for t, freq in self.doc_freqs.items():
                self.idf[t] = math.log((self.total_docs - freq + 0.5) / (freq + 0.5) + 1.0)

    def ensure_seeded(self) -> None:
        """Auto-seeds from mock references if corpus is currently empty."""
        if self.total_docs > 0:
            return
        try:
            mock_path = Path(settings.MOCK_DATABASE_PATH)
            if mock_path.exists():
                with open(mock_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sentences = []
                from app.services.segmenter import SentenceSegmenterService
                for doc in data:
                    segmented = SentenceSegmenterService.segment(doc.get("text", ""))
                    for idx, s in enumerate(segmented):
                        sentences.append({
                            "document_id": doc["id"],
                            "sentence_index": idx,
                            "text": s["text"],
                            "title": doc.get("title", "Unknown"),
                            "author": doc.get("author", "N/A"),
                            "source": doc.get("source", "N/A")
                        })
                self.add_documents(sentences)
                logger.info(f"Auto-seeded in-memory BM25 with {len(sentences)} reference sentences.")
        except Exception as e:
            logger.warning(f"Could not auto-seed in-memory BM25: {e}")

    def search(self, query_text: str, k: int = 20, job_id: str = None) -> list[dict]:
        self.ensure_seeded()
        if not self.total_docs or not query_text.strip():
            return []

        q_tokens = self.tokenize(query_text)
        if not q_tokens:
            return []

        scores = []
        for idx, doc in enumerate(self.corpus):
            doc_id = doc.get("document_id", "")
            if job_id:
                if not (doc_id.startswith("ref_") or doc_id.startswith(f"job_{job_id}_")):
                    continue

            tokens = self.tokenize(doc.get("text", ""))
            if not tokens:
                continue

            doc_len = len(tokens)
            t_counts: dict[str, int] = {}
            for t in tokens:
                t_counts[t] = t_counts.get(t, 0) + 1

            score = 0.0
            for qt in q_tokens:
                if qt in t_counts:
                    tf = t_counts[qt]
                    idf_val = self.idf.get(qt, 0.1)
                    numerator = idf_val * tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / (self.avgdl or 1.0)))
                    score += (numerator / denominator)

            if score > 0.0:
                scores.append((score, doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        top_k = scores[:k]
        return [
            {
                "document_id": doc["document_id"],
                "sentence_index": doc["sentence_index"],
                "text": doc["text"],
                "title": doc.get("title", "Unknown"),
                "author": doc.get("author", "N/A"),
                "source": doc.get("source", "N/A"),
                "score": float(sc)
            }
            for sc, doc in top_k
        ]


_in_memory_bm25 = InMemoryBM25()


def get_es_client() -> Elasticsearch:
    """Returns the Elasticsearch client singleton instance."""
    global _es_client
    if _es_client is None:
        headers = {
            "Accept": "application/vnd.elasticsearch+json; compatible-with=8",
            "Content-Type": "application/vnd.elasticsearch+json; compatible-with=8"
        }
        _es_client = Elasticsearch(settings.ELASTICSEARCH_URL, headers=headers)
    return _es_client


def is_es_available() -> bool:
    """Safely checks whether real Elasticsearch cluster is online."""
    try:
        es = get_es_client()
        return bool(es.ping())
    except Exception:
        return False


def initialize_es() -> None:
    """Creates the reference_sentences Elasticsearch index with custom BM25 mappings if online, or activates In-Memory BM25."""
    try:
        es = get_es_client()
        index_name = "reference_sentences"
        if not es.indices.exists(index=index_name):
            mappings = {
                "mappings": {
                    "properties": {
                        "document_id": { "type": "keyword" },
                        "sentence_index": { "type": "integer" },
                        "text": { "type": "text" },
                        "title": { "type": "keyword" },
                        "author": { "type": "keyword" },
                        "source": { "type": "keyword" }
                    }
                }
            }
            es.indices.create(index=index_name, body=mappings)
            logger.info(f"Created Elasticsearch index: '{index_name}' with mappings.")
        else:
            logger.info(f"Elasticsearch index '{index_name}' already exists.")
    except Exception as e:
        logger.info(f"Elasticsearch unavailable at {settings.ELASTICSEARCH_URL} ({e}). Seamlessly using embedded In-Memory BM25 Lexical Engine.")
        _in_memory_bm25.ensure_seeded()


def index_sentence_bulk(sentences: list[dict]) -> None:
    """Bulk indexes sentences into In-Memory BM25, and Elasticsearch if available."""
    # Always keep in-memory index up to date
    _in_memory_bm25.add_documents(sentences)

    try:
        es = get_es_client()
        index_name = "reference_sentences"
        actions = [
            {
                "_index": index_name,
                "_source": {
                    "document_id": s["document_id"],
                    "sentence_index": s["sentence_index"],
                    "text": s["text"],
                    "title": s.get("title", "Unknown"),
                    "author": s.get("author", "N/A"),
                    "source": s.get("source", "N/A")
                }
            }
            for s in sentences
        ]
        success, failed = bulk(es, actions)
        es.indices.refresh(index=index_name)
        logger.info(f"Successfully indexed {success} sentences to Elasticsearch.")
    except Exception as e:
        logger.debug(f"Elasticsearch bulk indexing skipped ({e}). In-Memory BM25 active.")


def search_sentences_bm25(query_text: str, k: int = 20, job_id: str = None) -> list[dict]:
    """
    Performs BM25 keyword matching against reference sentences.
    First tries Elasticsearch; falls back to embedded In-Memory BM25 engine.
    """
    if not query_text.strip():
        return []

    # 1. Try real Elasticsearch if available
    try:
        es = get_es_client()
        index_name = "reference_sentences"
        if job_id:
            query = {
                "query": {
                    "bool": {
                        "must": { "match": { "text": query_text } },
                        "filter": {
                            "bool": {
                                "should": [
                                    { "prefix": { "document_id": "ref_" } },
                                    { "prefix": { "document_id": f"job_{job_id}_" } }
                                ]
                            }
                        }
                    }
                },
                "size": k
            }
        else:
            query = {
                "query": { "match": { "text": query_text } },
                "size": k
            }

        response = es.search(index=index_name, body=query)
        hits = response["hits"]["hits"]
        if hits:
            return [
                {
                    "document_id": hit["_source"]["document_id"],
                    "sentence_index": hit["_source"]["sentence_index"],
                    "text": hit["_source"]["text"],
                    "title": hit["_source"].get("title", "Unknown"),
                    "author": hit["_source"].get("author", "N/A"),
                    "source": hit["_source"].get("source", "N/A"),
                    "score": hit["_score"]
                }
                for hit in hits
            ]
    except Exception as e:
        logger.debug(f"Elasticsearch query bypassed ({e}). Falling back to In-Memory BM25.")

    # 2. Fallback to embedded In-Memory BM25
    return _in_memory_bm25.search(query_text, k=k, job_id=job_id)
