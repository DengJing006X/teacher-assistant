"""
Knowledge base engine for the DingTalk/H5 test version.

Safety principle: retrieval must be conservative. If a teacher asks about a
topic that has no confirmed source text, the bot should return "unhit" instead
of forcing a weakly related answer.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Tuple


logger = logging.getLogger(__name__)


class KnowledgeBase:
    def __init__(self, config):
        self.config = config
        self.knowledge_dir = config.KNOWLEDGE_DIR
        self._vectorizer = None
        self._tfidf_matrix = None
        self._chunks = []
        self._metadatas = []

    def _is_allowed_category(self, category: str) -> bool:
        if category in {"敏感待审核", "职能白名单"}:
            return False
        if not self.config.TEST_MODE:
            return True
        return category in self.config.ALLOWED_KNOWLEDGE_CATEGORIES

    def _is_allowed_file(self, file_path: Path) -> bool:
        name = file_path.name.lower()
        blocked_keywords = [
            "测试版可上线知识清单",
            "测试版不可上线知识清单",
            "测试版统一回答模板",
            "测试版未命中话术",
            "测试版敏感问题拦截话术",
            "readme",
            "skill",
            "status",
            "缺口",
            "样例",
            "规范",
            "说明",
        ]
        return not any(keyword in name for keyword in blocked_keywords)

    def _load_documents(self) -> List[dict]:
        docs = []
        if not self.knowledge_dir.exists():
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)
            return docs

        for file_path in sorted(self.knowledge_dir.glob("**/*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in [".md", ".txt"]:
                continue

            relative = file_path.relative_to(self.knowledge_dir)
            category = relative.parent.name if relative.parent.name != "." else ""
            if not self._is_allowed_category(category):
                logger.info("Skip out-of-scope file: %s", file_path.name)
                continue
            if not self._is_allowed_file(file_path):
                logger.info("Skip helper or template file: %s", file_path.name)
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                docs.append(
                    {
                        "content": content,
                        "filename": file_path.name,
                        "category": category,
                        "path": str(file_path),
                    }
                )
                logger.info("Loaded file: [%s] %s", category, file_path.name)
            except Exception as e:
                logger.warning("Failed to read file %s: %s", file_path.name, e)
        return docs

    def _split_text(self, text: str) -> List[str]:
        text = text.strip()
        if not text:
            return []

        sections = re.split(r"(?=^##\s+)", text, flags=re.MULTILINE)
        chunks = []
        for section in sections:
            section = section.strip()
            if section and section.startswith("## "):
                chunks.append(section)

        if chunks:
            return chunks

        paragraphs = re.split(r"\n\s*\n", text)
        current = ""
        fallback_chunks = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) < self.config.CHUNK_SIZE:
                current += para + "\n\n"
            else:
                if current:
                    fallback_chunks.append(current.strip())
                current = para + "\n\n"

        if current:
            fallback_chunks.append(current.strip())

        return fallback_chunks or [text]

    def initialize(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        import jieba

        logger.info("Initializing knowledge base...")
        docs = self._load_documents()

        self._chunks = []
        self._metadatas = []
        self._vectorizer = None
        self._tfidf_matrix = None

        if not docs:
            logger.warning("No in-scope documents found under knowledge/")
            return

        for doc in docs:
            chunks = self._split_text(doc["content"])
            for i, chunk in enumerate(chunks):
                self._chunks.append(chunk)
                self._metadatas.append(
                    {
                        "filename": doc["filename"],
                        "category": doc.get("category", ""),
                        "chunk_index": i,
                    }
                )

        if not self._chunks:
            logger.warning("No chunks were produced from in-scope documents")
            return

        def tokenize(text: str) -> str:
            return " ".join(jieba.cut(text))

        tokenized = [tokenize(c) for c in self._chunks]
        self._vectorizer = TfidfVectorizer(
            token_pattern=r"(?u)\b\w+\b",
            max_features=50000,
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(tokenized)

        logger.info(
            "Knowledge base ready: %s documents, %s chunks",
            len(docs),
            len(self._chunks),
        )

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"[\s\W_]+", "", text.lower(), flags=re.UNICODE)

    def _title_of(self, chunk: str) -> str:
        first_line = chunk.splitlines()[0].strip() if chunk.splitlines() else ""
        return first_line[3:].strip() if first_line.startswith("## ") else first_line

    def _meaningful_terms(self, text: str) -> set[str]:
        import jieba

        stop_words = {
            "老师",
            "怎么",
            "怎么办",
            "如何",
            "可以",
            "能不能",
            "是否",
            "什么",
            "这个",
            "那个",
            "一下",
            "需要",
            "进行",
            "处理",
            "问题",
            "如果",
            "当前",
            "公司",
            "相关",
        }
        terms = set()
        for token in jieba.cut(text):
            token = token.strip().lower()
            if not token or token in stop_words:
                continue
            if len(token) == 1 and not re.match(r"[a-z0-9]", token):
                continue
            terms.add(token)
        return terms

    def _has_enough_overlap(self, query: str, chunk: str, score: float) -> bool:
        query_terms = self._meaningful_terms(query)
        if not query_terms:
            return False

        title = self._title_of(chunk)
        searchable = f"{title}\n{chunk}".lower()
        overlap = {term for term in query_terms if term in searchable}

        if len(overlap) >= 2:
            return True
        if len(overlap) == 1 and score >= 0.22:
            return True
        return False

    def search(self, query: str, top_k: int = None) -> List[Tuple[str, float, str]]:
        if self._vectorizer is None or self._tfidf_matrix is None:
            self.initialize()

        if self._vectorizer is None or self._tfidf_matrix is None:
            return []

        if top_k is None:
            top_k = self.config.RETRIEVAL_COUNT

        try:
            import jieba
            from sklearn.metrics.pairwise import cosine_similarity

            normalized_query = self._normalize_text(query)

            direct_hits = []
            for i, chunk in enumerate(self._chunks):
                title = self._title_of(chunk)
                normalized_title = self._normalize_text(title)
                if normalized_query and (
                    normalized_query in normalized_title or normalized_title in normalized_query
                ):
                    direct_hits.append(
                        (
                            self._chunks[i],
                            1.0,
                            self._metadatas[i]["filename"],
                        )
                    )

            if direct_hits:
                return direct_hits[::-1][:top_k]

            def tokenize(text: str) -> str:
                return " ".join(jieba.cut(text))

            query_vec = self._vectorizer.transform([tokenize(query)])
            similarities = cosine_similarity(query_vec, self._tfidf_matrix)[0]

            results = []
            for i, score in enumerate(similarities):
                score = float(score)
                if score < self.config.SIMILARITY_THRESHOLD:
                    continue
                chunk = self._chunks[i]
                if not self._has_enough_overlap(query, chunk, score):
                    logger.info("Reject weak hit score=%.3f title=%s", score, self._title_of(chunk))
                    continue
                results.append((chunk, score, self._metadatas[i]["filename"]))

            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def get_document_count(self) -> int:
        return len(set(m["filename"] for m in self._metadatas)) if self._metadatas else 0

    def get_chunk_count(self) -> int:
        return len(self._chunks)

    def get_all_chunks(self) -> List[Tuple[str, float, str]]:
        if not self._chunks:
            return []
        return [
            (self._chunks[i], 0.0, self._metadatas[i]["filename"])
            for i in range(len(self._chunks))
        ]
