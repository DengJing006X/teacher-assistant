"""
Knowledge base engine for the H5 test version.
Only loads allowed categories for the current test scope.
"""

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
                docs.append({
                    "content": content,
                    "filename": file_path.name,
                    "category": category,
                    "path": str(file_path),
                })
                logger.info("Loaded file: [%s] %s", category, file_path.name)
            except Exception as e:
                logger.warning("Failed to read file %s: %s", file_path.name, e)
        return docs

    def _split_text(self, text: str) -> List[str]:
        chunks = []
        paragraphs = re.split(r"\n\s*\n", text)
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) < self.config.CHUNK_SIZE:
                current += para + "\n\n"
            else:
                if current:
                    chunks.append(current.strip())
                current = para + "\n\n"

        if current:
            chunks.append(current.strip())

        if not chunks and text.strip():
            chunks = [text.strip()]

        return chunks

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
                self._metadatas.append({
                    "filename": doc["filename"],
                    "category": doc.get("category", ""),
                    "chunk_index": i,
                })

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

            def tokenize(text: str) -> str:
                return " ".join(jieba.cut(text))

            query_vec = self._vectorizer.transform([tokenize(query)])
            similarities = cosine_similarity(query_vec, self._tfidf_matrix)[0]

            results = []
            for i, score in enumerate(similarities):
                if score >= self.config.SIMILARITY_THRESHOLD:
                    results.append((
                        self._chunks[i],
                        float(score),
                        self._metadatas[i]["filename"],
                    ))

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
