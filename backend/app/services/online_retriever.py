import logging
import asyncio
import httpx
import xml.etree.ElementTree as ET
from collections import Counter
from app.config import settings
from app.services.segmenter import SentenceSegmenterService
from app.services.database import DatabaseService
from app.services.elasticsearch_client import get_es_client, index_sentence_bulk
from app.services.matcher import SemanticMatcher

logger = logging.getLogger(__name__)

class OnlineRetrieverService:
    """Manages dynamic query generation, external academic API fetching, and JIT ephemeral caching."""

    @classmethod
    def extract_search_queries(cls, text: str, num_queries: int = 8) -> list[str]:
        """
        Analyzes document text using spaCy to extract high-entropy phrases for searching external APIs,
        distributing candidate selection across different parts of the document.
        """
        if not text or not text.strip():
            return []

        try:
            nlp = SentenceSegmenterService.get_nlp()
            # Cloud memory guard: cap to first 12,000 characters (Abstract/Intro) to prevent RAM explosion
            scoped_text = text[:12000] if len(text) > 12000 else text
            doc = nlp(scoped_text)
            
            # Group noun chunks by sentence index
            sentences = list(doc.sents)
            sent_chunks = []
            for i, sent in enumerate(sentences):
                chunks_in_sent = []
                for chunk in sent.noun_chunks:
                    chunk_clean = " ".join([
                        token.text.lower() 
                        for token in chunk 
                        if not token.is_stop and not token.is_punct and token.is_alpha
                    ]).strip()
                    
                    words = chunk_clean.split()
                    if 2 <= len(words) <= 4 and chunk_clean:
                        chunks_in_sent.append(chunk_clean)
                if chunks_in_sent:
                    sent_chunks.append((i, chunks_in_sent))
            
            queries = []
            if sent_chunks:
                num_sents = len(sent_chunks)
                if num_sents <= num_queries:
                    # Pick the longest chunk from each sentence
                    for _, chunks in sent_chunks:
                        chunks.sort(key=len, reverse=True)
                        for c in chunks:
                            if c not in queries:
                                queries.append(c)
                                break
                else:
                    # Distribute chunk selection across the document sentences
                    indices_to_pick = []
                    if num_queries == 1:
                        indices_to_pick = [0]
                    else:
                        for i in range(num_queries):
                            idx = int(i * (num_sents - 1) / (num_queries - 1))
                            if idx not in indices_to_pick:
                                indices_to_pick.append(idx)
                                
                    for idx in indices_to_pick:
                        if idx < len(sent_chunks):
                            chunks = sent_chunks[idx][1]
                            chunks.sort(key=len, reverse=True)
                            for c in chunks:
                                if c not in queries:
                                    queries.append(c)
                                    break

            # Fallback if we don't have enough queries
            if len(queries) < num_queries:
                all_chunks = []
                for _, chunks in sent_chunks:
                    all_chunks.extend(chunks)
                counts = Counter(all_chunks)
                for item, _ in counts.most_common():
                    if len(queries) >= num_queries:
                        break
                    if item not in queries:
                        queries.append(item)

            # Fallback to frequent words if we still don't have enough queries
            if len(queries) < num_queries:
                words = [
                    token.text.lower() 
                    for token in doc 
                    if not token.is_stop and token.is_alpha and len(token.text) > 4
                ]
                word_counts = Counter(words)
                for word, _ in word_counts.most_common(num_queries * 2):
                    if len(queries) >= num_queries:
                        break
                    if word not in queries:
                        queries.append(word)

            # Absolute fallback: first few words of text
            if not queries:
                fallback_words = [w for w in text.split() if w.isalpha()][:5]
                if fallback_words:
                    queries.append(" ".join(fallback_words).lower())

            return queries[:num_queries]
        except Exception as e:
            logger.error(f"Failed to extract search queries from document: {e}")
            return []

    @classmethod
    async def fetch_arxiv_candidates(cls, query: str, limit: int = 15) -> list[dict]:
        """Queries the arXiv API for matching academic preprints with retries."""
        url = "https://export.arxiv.org/api/query"
        # Search all fields with flexible query terms without strict quote nesting
        clean_q = query.replace('"', '').strip()
        params = {
            "search_query": f'all:{clean_q}',
            "max_results": limit
        }
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        ns = {'atom': 'http://www.w3.org/2005/Atom'}
                        try:
                            if "xml" not in response.headers.get("content-type", "").lower():
                                return []
                            root = ET.fromstring(response.content)
                        except ET.ParseError:
                            return []
                            
                        entries = root.findall('atom:entry', ns)
                        candidates = []
                        for entry in entries:
                            title_elem = entry.find('atom:title', ns)
                            summary_elem = entry.find('atom:summary', ns)
                            id_elem = entry.find('atom:id', ns)
                            
                            if title_elem is None or summary_elem is None or id_elem is None:
                                continue
                                
                            title = title_elem.text.strip().replace("\n", " ")
                            abstract = summary_elem.text.strip().replace("\n", " ")
                            paper_url = id_elem.text.strip()
                            paper_id = paper_url.split('/abs/')[-1].split('v')[0]
                            
                            authors = [
                                auth.find('atom:name', ns).text.strip() 
                                for auth in entry.findall('atom:author', ns) 
                                if auth.find('atom:name', ns) is not None
                            ]
                            author_str = ", ".join(authors) if authors else "N/A"
                            
                            candidates.append({
                                "doc_id": f"arxiv_{paper_id}",
                                "title": title,
                                "author": author_str,
                                "source": f"arXiv Preprint ({paper_url})",
                                "text": abstract
                            })
                        return candidates
            except Exception as e:
                logger.warning(f"arXiv candidate search error for '{query}': {e}")
        return []

    @classmethod
    async def fetch_crossref_candidates(cls, query: str, limit: int = 15) -> list[dict]:
        """Queries the Crossref Academic API for matching DOI peer-reviewed journal papers and abstracts."""
        url = "https://api.crossref.org/works"
        params = {
            "query": query.replace('"', '').strip(),
            "rows": limit,
            "select": "DOI,title,author,abstract,container-title,published"
        }
        headers = {
            "User-Agent": "LemmaAcademicIntegrity/2.0 (mailto:contact@lemma.ai)"
        }
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    items = response.json().get("message", {}).get("items", [])
                    candidates = []
                    for item in items:
                        title_list = item.get("title", [])
                        title = title_list[0] if title_list else "Academic Reference"
                        abstract = item.get("abstract", "") or ""
                        
                        # Strip jats xml tags if present
                        if abstract:
                            import re
                            abstract = re.sub(r'<[^>]+>', ' ', abstract).strip()
                            
                        # If abstract is absent, use title and venue context
                        if not abstract or len(abstract) < 20:
                            venue = item.get("container-title", [""])[0] if item.get("container-title") else ""
                            abstract = f"{title}. Published in {venue}." if venue else title
                            
                        doi = item.get("DOI", "unknown")
                        venue = item.get("container-title", ["Academic Publisher"])[0] if item.get("container-title") else "Peer-Reviewed Journal"
                        
                        # Authors
                        authors = []
                        for a in item.get("author", []):
                            family = a.get("family", "")
                            given = a.get("given", "")
                            if family:
                                authors.append(f"{given} {family}".strip())
                        author_str = ", ".join(authors) if authors else "Scholarly Research Team"
                        
                        candidates.append({
                            "doc_id": f"crossref_{doi.replace('/', '_')}",
                            "title": title,
                            "author": author_str,
                            "source": f"{venue} (DOI: {doi})",
                            "text": abstract
                        })
                    return candidates
        except Exception as e:
            logger.warning(f"Crossref search error for '{query}': {e}")
        return []

    @classmethod
    async def fetch_wikipedia_candidates(cls, query: str, limit: int = 5) -> list[dict]:
        """Queries the Wikipedia Encyclopedia API for matching academic concepts and text excerpts."""
        url = "https://en.wikipedia.org/w/api.php"
        headers = {
            "User-Agent": "LemmaAcademicIntegrity/2.0 (contact@lemma.ai)"
        }
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                search_res = await client.get(url, params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query.replace('"', '').strip(),
                    "format": "json",
                    "srlimit": limit
                })
                if search_res.status_code == 200:
                    results = search_res.json().get("query", {}).get("search", [])
                    titles = [r.get("title") for r in results if r.get("title")]
                    if not titles:
                        return []
                    
                    # Fetch extracts for found titles
                    extract_res = await client.get(url, params={
                        "action": "query",
                        "prop": "extracts",
                        "explaintext": "1",
                        "titles": "|".join(titles[:limit]),
                        "format": "json"
                    })
                    if extract_res.status_code == 200:
                        pages = extract_res.json().get("query", {}).get("pages", {})
                        candidates = []
                        for pid, pdata in pages.items():
                            title = pdata.get("title", "Wikipedia Article")
                            extract = pdata.get("extract", "")
                            if extract and len(extract) > 30:
                                candidates.append({
                                    "doc_id": f"wiki_{pid}",
                                    "title": f"Wikipedia: {title}",
                                    "author": "Wikipedia Contributors",
                                    "source": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                                    "text": extract[:2500]
                                })
                        return candidates
        except Exception as e:
            logger.warning(f"Wikipedia search error for '{query}': {e}")
        return []

    @classmethod
    async def fetch_semantic_scholar_candidates(cls, query: str, limit: int = 15) -> list[dict]:
        """Queries the Semantic Scholar search API for matching academic papers."""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query.replace('"', '').strip(),
            "limit": limit,
            "fields": "title,authors,venue,year,abstract"
        }
        
        headers = {}
        if settings.SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY
            
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    papers = data.get("data", [])
                    
                    candidates = []
                    for paper in papers:
                        paper_id = paper.get("paperId")
                        title = paper.get("title")
                        abstract = paper.get("abstract")
                        
                        if not paper_id or not title or not abstract:
                            continue
                            
                        authors = [auth.get("name") for auth in paper.get("authors", []) if auth.get("name")]
                        author_str = ", ".join(authors) if authors else "N/A"
                        venue = paper.get("venue", "Academic Publication")
                        year = paper.get("year", "N/A")
                        
                        candidates.append({
                            "doc_id": f"semschol_{paper_id}",
                            "title": title,
                            "author": author_str,
                            "source": f"{venue}, {year}",
                            "text": abstract
                        })
                    return candidates
        except Exception as e:
            logger.warning(f"Semantic Scholar candidate search error: {e}")
        return []

    @classmethod
    async def fetch_openalex_candidates(cls, query: str, limit: int = 15) -> list[dict]:
        """Queries OpenAlex Academic API for matching research works, reconstructs abstracts from inverted indices."""
        clean_q = query.replace('"', '').strip()
        url = "https://api.openalex.org/works"
        params = {
            "search": clean_q,
            "per-page": limit,
            "select": "id,title,doi,publication_year,primary_location,authorships,abstract_inverted_index"
        }
        headers = {
            "User-Agent": "LemmaAcademicIntegrity/2.0 (mailto:admin@lemma.ai)"
        }
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    candidates = []
                    for item in results:
                        title = item.get("title") or "Scholarly Publication"
                        inv = item.get("abstract_inverted_index")
                        abstract = ""
                        if inv:
                            pos_word_pairs = []
                            for word, positions in inv.items():
                                for p in positions:
                                    pos_word_pairs.append((p, word))
                            pos_word_pairs.sort(key=lambda x: x[0])
                            abstract = " ".join(w for _, w in pos_word_pairs)
                        
                        if not abstract or len(abstract) < 30:
                            venue_name = ""
                            if item.get("primary_location") and item["primary_location"].get("source"):
                                venue_name = item["primary_location"]["source"].get("display_name", "")
                            abstract = f"{title}. Published in {venue_name}." if venue_name else title
                            
                        raw_id = item.get("id", "").split("/")[-1] or "work"
                        doi = item.get("doi") or f"https://openalex.org/{raw_id}"
                        
                        authors = []
                        for a in item.get("authorships", []):
                            author_obj = a.get("author", {})
                            name = author_obj.get("display_name")
                            if name:
                                authors.append(name)
                        author_str = ", ".join(authors[:4]) if authors else "Academic Research Team"
                        
                        candidates.append({
                            "doc_id": f"openalex_{raw_id}",
                            "title": title,
                            "author": author_str,
                            "source": f"OpenAlex Academic Works ({doi})",
                            "text": abstract
                        })
                    return candidates
        except Exception as e:
            logger.warning(f"OpenAlex candidate search error for '{query}': {e}")
        return []

    @classmethod
    async def get_online_candidates(cls, queries: list[str], limit_per_query: int = None) -> list[dict]:
        """Fetches and merges candidates concurrently across OpenAlex, Crossref, arXiv, Wikipedia, and Semantic Scholar."""
        if limit_per_query is None:
            limit_per_query = settings.MAX_ONLINE_CANDIDATES_PER_QUERY
            
        all_candidates = []
        seen_ids = set()
        seen_titles = set()
        
        tasks = []
        for query in queries[:8]:
            tasks.append(cls.fetch_openalex_candidates(query, limit=10))
            tasks.append(cls.fetch_crossref_candidates(query, limit=10))
            tasks.append(cls.fetch_arxiv_candidates(query, limit=10))
            tasks.append(cls.fetch_wikipedia_candidates(query, limit=4))
            tasks.append(cls.fetch_semantic_scholar_candidates(query, limit=8))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for cand_list in results:
            if isinstance(cand_list, list):
                for cand in cand_list:
                    cand_id = cand.get("doc_id", "")
                    title_lower = cand.get("title", "").lower().strip()
                    
                    if cand_id and cand_id not in seen_ids and title_lower not in seen_titles:
                        seen_ids.add(cand_id)
                        seen_titles.add(title_lower)
                        all_candidates.append(cand)
                        
        return all_candidates

    @classmethod
    async def seed_ephemeral_candidates(cls, job_id: str, candidates: list[dict]) -> None:
        """
        Embeds, segments, and writes candidates to PostgreSQL and Elasticsearch using job-isolated IDs.
        """
        if not candidates:
            return

        logger.info(f"Seeding {len(candidates)} ephemeral candidates for job: {job_id}")
        
        # 1. Segment candidates into sentences
        flat_sentences = []
        for cand in candidates:
            doc_id = f"job_{job_id}_{cand['doc_id']}"
            
            # Write document metadata to PostgreSQL
            try:
                DatabaseService.insert_reference_document(
                    doc_id=doc_id,
                    title=cand["title"],
                    author=cand["author"],
                    source=cand["source"]
                )
            except Exception as e:
                logger.error(f"Failed to write ephemeral document {doc_id} metadata: {e}")
                continue

            sentences = SentenceSegmenterService.segment(cand["text"])
            for idx, s in enumerate(sentences):
                flat_sentences.append({
                    "document_id": doc_id,
                    "sentence_index": idx,
                    "text": s["text"]
                })

        if not flat_sentences:
            return

        # 2. Generate vector embeddings using SemanticMatcher
        try:
            model = SemanticMatcher.get_model()
            corpus = [s["text"] for s in flat_sentences]
            embeddings = model.encode(corpus, show_progress_bar=False)
            
            for s, emb in zip(flat_sentences, embeddings):
                s["embedding"] = emb.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embeddings for ephemeral sentences: {e}")
            return

        # 3. Dual-Write to PostgreSQL and Elasticsearch
        try:
            DatabaseService.insert_reference_sentences(flat_sentences)
            index_sentence_bulk(flat_sentences)
            logger.info(f"Successfully cached {len(flat_sentences)} sentences locally for job: {job_id}")
        except Exception as e:
            logger.error(f"Dual-Write caching failed for job {job_id}: {e}")

    @classmethod
    def prune_cache(cls, job_id: str) -> None:
        """
        Deletes all PostgreSQL and Elasticsearch candidate records associated with the specified job_id.
        """
        logger.info(f"Pruning ephemeral cache for job: {job_id}")
        
        # 1. Prune from PostgreSQL
        try:
            with DatabaseService.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Cascade deletes sentences via foreign key on documents
                    cursor.execute("DELETE FROM documents WHERE id LIKE %s;", (f"job_{job_id}_%",))
                conn.commit()
            logger.info(f"Pruned PostgreSQL records for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to prune PostgreSQL cache for job {job_id}: {e}")

        # 2. Prune from Elasticsearch
        try:
            es = get_es_client()
            index_name = "reference_sentences"
            if es.indices.exists(index=index_name):
                query = {
                    "query": {
                        "prefix": {
                            "document_id": f"job_{job_id}_"
                        }
                    }
                }
                res = es.delete_by_query(index=index_name, body=query)
                es.indices.refresh(index=index_name)
                deleted = res.get("deleted", 0)
                logger.info(f"Pruned {deleted} Elasticsearch sentences for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to prune Elasticsearch cache for job {job_id}: {e}")
