from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from openai import OpenAI

from app.config import get_settings
from app.models import ParsedAsset, RetrievalHit
from app.services.parser import parse_file
from app.utils.paths import ensure_project_directories


MANIFEST_FILENAME = "manifest.json"
INDEX_FILENAME = "kb_index.faiss"
METADATA_FILENAME = "kb_metadata.json"

SUBJECT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("chemistry", ("化学", "nahco3", "碳酸氢钠", "碳酸钠", "硫酸", "氯", "溴", "碘", "氨", "铵盐", "铁盐", "亚铁盐")),
    ("physics", ("物理", "电路", "量子", "rlc", "电感", "电容", "正弦稳态", "互感")),
    ("math", ("数学", "代数", "函数", "集合", "逻辑", "证明", "关系", "几何")),
    ("english", ("英语", "english", "unit", "grammar", "present perfect")),
    ("history", ("历史", "history", "工业革命", "industrial revolution", "革命", "revolution", "战争", "民族解放", "新民主主义", "社会主义", "当代中国", "史料")),
    ("geography", ("地理", "地图", "地貌", "气候", "经纬")),
    ("politics", ("政治", "思想道德", "法治", "经济生活", "哲学")),
    ("biology", ("生物", "细胞", "遗传", "生态", "酶")),
    ("information-technology", ("人工智能", "机器学习", "计算机", "word", "excel", "win10", "操作系统", "图像", "视频处理", "数字图像", "软硬件")),
    ("chinese", ("语文", "古诗", "阅读", "作文", "修辞")),
)
STAGE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("primary-school", ("小学",)),
    ("middle-school", ("初中", "初一", "初二", "初三", "中考")),
    ("high-school", ("高中", "高一", "高二", "高三", "高考", "必修", "选修")),
    ("college", ("大学", "高等", "课程", "章", "专题")),
    ("vocational", ("职业", "职教")),
)


def _sanitize_namespace(namespace: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", namespace.strip())
    return cleaned or "default"


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    groups = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", lowered)
    tokens: list[str] = []
    for group in groups:
        tokens.append(group)
        if re.fullmatch(r"[\u4e00-\u9fff]+", group):
            tokens.extend(list(group))
    return tokens or [lowered[:50] or "empty"]


def _normalize_tag_value(value: str | None) -> str | None:
    normalized = " ".join(str(value or "").split()).strip().lower()
    return normalized or None


def _keyword_score(text: str, keywords: tuple[str, ...]) -> float:
    lowered = text.lower()
    score = 0.0
    for keyword in keywords:
        token = keyword.lower().strip()
        if not token:
            continue
        if token in lowered:
            score += 3.0 if len(token) >= 4 else 1.5
    return score


def _infer_subject_tag(path: Path, text: str) -> str | None:
    path_text = str(path).lower()
    body_text = text.lower()
    best_tag: str | None = None
    best_score = 0.0

    for tag, keywords in SUBJECT_RULES:
        score = _keyword_score(path_text, keywords) * 2.0
        score += _keyword_score(body_text, keywords)
        if score > best_score:
            best_score = score
            best_tag = tag

    return best_tag if best_score >= 1.5 else None


def _infer_stage_tag(path: Path, text: str) -> str | None:
    combined = f"{str(path).lower()} {text.lower()}"
    best_tag: str | None = None
    best_score = 0.0

    for tag, keywords in STAGE_RULES:
        score = _keyword_score(combined, keywords)
        if score > best_score:
            best_score = score
            best_tag = tag

    return best_tag if best_score >= 1.5 else None


def _derive_topic_hint(path: Path) -> str:
    stem = path.stem.replace("_", " ").strip()
    stem = re.sub(r"^[\d０-９]+[.\-、\s]*", "", stem)
    stem = re.sub(r"\s{2,}", " ", stem).strip()
    return stem[:80] or path.name


def _normalize_filter_values(values: str | list[str] | tuple[str, ...] | None) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        values = [values]
    normalized = {
        item
        for item in (_normalize_tag_value(value) for value in values)
        if item
    }
    return normalized


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    if len(normalized) <= chunk_size:
        return [normalized]

    step = max(chunk_size - overlap, 1)
    chunks: list[str] = []
    for start in range(0, len(normalized), step):
        chunk = normalized[start : start + chunk_size].strip()
        if not chunk:
            continue
        if len(chunk) < 40 and chunks:
            chunks[-1] = f"{chunks[-1]} {chunk}".strip()
            continue
        chunks.append(chunk)
        if start + chunk_size >= len(normalized):
            break
    return chunks


class LocalHashEmbeddingProvider:
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension
        self.name = "local-hash"

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in _tokenize(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "little") % self.dimension
                sign = -1.0 if digest[4] % 2 else 1.0
                weight = 1.0 + min(len(token), 12) / 12.0
                vectors[row, index] += sign * weight

            norm = float(np.linalg.norm(vectors[row]))
            if norm == 0.0:
                vectors[row, 0] = 1.0
                norm = 1.0
            vectors[row] /= norm
        return vectors


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.name = f"openai:{model}"
        self.dimension: int | None = None

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        response = self.client.embeddings.create(model=self.model, input=texts)
        vectors = np.array([item.embedding for item in response.data], dtype=np.float32)
        if self.dimension is None:
            self.dimension = vectors.shape[1]
        faiss.normalize_L2(vectors)
        return vectors


class LocalKnowledgeBase:
    def __init__(
        self,
        store_dir: Path | None = None,
        namespace: str | None = None,
        embedding_backend: str | None = None,
    ) -> None:
        settings = get_settings()
        ensure_project_directories()

        backend = (embedding_backend or settings.embeddings_backend).strip().lower()
        if store_dir is not None:
            self.store_dir = Path(store_dir)
        elif namespace:
            self.store_dir = settings.vector_store_dir / _sanitize_namespace(namespace)
        else:
            self.store_dir = settings.vector_store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.store_dir / INDEX_FILENAME
        self.metadata_path = self.store_dir / METADATA_FILENAME
        self.manifest_path = self.store_dir / MANIFEST_FILENAME

        if backend == "openai" and settings.openai_api_key:
            self.embedding_provider: OpenAIEmbeddingProvider | LocalHashEmbeddingProvider = (
                OpenAIEmbeddingProvider(
                    api_key=settings.openai_api_key,
                    model=settings.embeddings_model,
                )
            )
            self.dimension = None
        else:
            self.embedding_provider = LocalHashEmbeddingProvider(settings.local_embedding_dim)
            self.dimension = settings.local_embedding_dim

        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap
        self.default_top_k = settings.rag_default_top_k
        self.index: faiss.Index | None = None
        self.metadata: list[dict[str, Any]] = []

    def _manifest_payload(self) -> dict[str, Any]:
        dimension = self.dimension or getattr(self.embedding_provider, "dimension", None)
        return {
            "embedding_backend": self.embedding_provider.name,
            "dimension": dimension,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

    def _load(self) -> None:
        if self.index is not None:
            return

        if self.index_path.exists() and self.metadata_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            manifest = (
                json.loads(self.manifest_path.read_text(encoding="utf-8"))
                if self.manifest_path.exists()
                else {}
            )
            manifest_dimension = manifest.get("dimension")
            if self.dimension is None:
                self.dimension = manifest_dimension
            elif manifest_dimension and self.dimension != manifest_dimension:
                raise ValueError("Embedding dimension does not match the existing vector store")
            return

        if self.dimension is None:
            raise ValueError(
                "OpenAI-backed vector store must be initialized by ingesting documents first"
            )
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []

    def _save(self) -> None:
        if self.index is None:
            return
        faiss.write_index(self.index, str(self.index_path))
        self.metadata_path.write_text(
            json.dumps(self.metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.manifest_path.write_text(
            json.dumps(self._manifest_payload(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _reset(self) -> None:
        if self.dimension is None:
            raise ValueError("Cannot reset vector store before determining embedding dimension")
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []

    def _parsed_asset_from_path(self, path: Path) -> ParsedAsset:
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if "resource_type" in payload and "source_path" in payload:
                return ParsedAsset.model_validate(payload)
        return parse_file(path)

    def _build_chunk_records(self, parsed_asset: ParsedAsset) -> list[dict[str, Any]]:
        base_text = parsed_asset.extracted_text or parsed_asset.text_preview
        if not _normalize_text(base_text):
            return []

        source_path = Path(parsed_asset.source_path)
        inferred_subject = _normalize_tag_value(
            str(parsed_asset.metadata.get("subject_tag")) if parsed_asset.metadata.get("subject_tag") is not None else None
        ) or _infer_subject_tag(source_path, base_text[:2400])
        inferred_stage = _normalize_tag_value(
            str(parsed_asset.metadata.get("stage_tag")) if parsed_asset.metadata.get("stage_tag") is not None else None
        ) or _infer_stage_tag(source_path, base_text[:1800])
        source_filename = str(parsed_asset.metadata.get("filename") or source_path.name)
        topic_hint = _normalize_text(
            str(parsed_asset.metadata.get("topic_hint") or parsed_asset.metadata.get("title") or _derive_topic_hint(source_path))
        )[:80]
        record_metadata = dict(parsed_asset.metadata)
        record_metadata.setdefault("filename", source_filename)
        record_metadata.setdefault("title", topic_hint)
        if inferred_subject:
            record_metadata["subject_tag"] = inferred_subject
        if inferred_stage:
            record_metadata["stage_tag"] = inferred_stage
        if topic_hint:
            record_metadata["topic_hint"] = topic_hint

        records: list[dict[str, Any]] = []
        for index, chunk in enumerate(
            chunk_text(base_text, self.chunk_size, self.chunk_overlap),
            start=1,
        ):
            chunk_hash = hashlib.blake2b(
                f"{parsed_asset.source_path}:{index}:{chunk}".encode("utf-8"),
                digest_size=10,
            ).hexdigest()
            records.append(
                {
                    "chunk_id": chunk_hash,
                    "asset_id": parsed_asset.parsed_id,
                    "content": chunk,
                    "page_label": str(index),
                    "source_path": parsed_asset.source_path,
                    "source_filename": source_filename,
                    "resource_type": parsed_asset.resource_type.value,
                    "subject_tag": inferred_subject,
                    "stage_tag": inferred_stage,
                    "topic_hint": topic_hint,
                    "metadata": record_metadata,
                }
            )
        return records

    def ingest_paths(self, paths: list[Path], reset: bool = False) -> dict[str, Any]:
        self._load()
        if reset:
            self._reset()

        processed_files = 0
        skipped_files: list[str] = []
        new_records: list[dict[str, Any]] = []

        for path in paths:
            try:
                parsed_asset = self._parsed_asset_from_path(path)
            except Exception:
                skipped_files.append(str(path))
                continue

            records = self._build_chunk_records(parsed_asset)
            if not records:
                skipped_files.append(str(path))
                continue

            processed_files += 1
            new_records.extend(records)

        if new_records:
            vectors = self.embedding_provider.embed_texts(
                [record["content"] for record in new_records]
            )
            if self.dimension is None:
                self.dimension = vectors.shape[1]
                self._reset()
            self.index.add(vectors)
            self.metadata.extend(new_records)
            self._save()

        return {
            "processed_files": processed_files,
            "skipped_files": skipped_files,
            "chunk_count": len(new_records),
            "total_chunks_in_store": len(self.metadata),
            "embedding_backend": self.embedding_provider.name,
        }

    def ingest_default_sources(
        self,
        source_dir: str | None = None,
        include_parsed_assets: bool = False,
        session_id: str | None = None,
        reset: bool = False,
    ) -> dict[str, Any]:
        settings = get_settings()
        paths: list[Path] = []

        kb_dir = Path(source_dir) if source_dir else settings.knowledge_base_dir
        if kb_dir.exists():
            paths.extend(
                path
                for path in kb_dir.rglob("*")
                if path.is_file() and not path.name.startswith(".")
            )

        if include_parsed_assets:
            parsed_root = (
                settings.parsed_data_dir / session_id
                if session_id
                else settings.parsed_data_dir
            )
            if parsed_root.exists():
                paths.extend(parsed_root.rglob("*.json"))

        deduped_paths = list(dict.fromkeys(path.resolve() for path in paths))
        return self.ingest_paths(deduped_paths, reset=reset)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        *,
        subject_filter: str | list[str] | None = None,
        stage_filter: str | list[str] | None = None,
        topic_keywords: list[str] | None = None,
    ) -> list[RetrievalHit]:
        normalized = _normalize_text(query)
        if not normalized:
            return []

        self._load()
        if self.index is None or self.index.ntotal == 0:
            return []

        search_top_k = top_k or self.default_top_k
        subject_filters = _normalize_filter_values(subject_filter)
        stage_filters = _normalize_filter_values(stage_filter)
        clean_topic_keywords = [
            term
            for term in (_normalize_text(item) for item in (topic_keywords or []))
            if term
        ]
        query_vector = self.embedding_provider.embed_texts([normalized])
        candidate_limit = min(
            self.index.ntotal,
            max(search_top_k * 30, 200) if (subject_filters or stage_filters or clean_topic_keywords) else max(search_top_k, 20),
        )
        scores, indices = self.index.search(query_vector, candidate_limit)

        ranked_hits: list[RetrievalHit] = []
        for score, index in zip(scores[0], indices[0]):
            if index < 0 or index >= len(self.metadata):
                continue
            item = self.metadata[index]
            metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
            item_subject = _normalize_tag_value(item.get("subject_tag") or metadata.get("subject_tag"))
            item_stage = _normalize_tag_value(item.get("stage_tag") or metadata.get("stage_tag"))
            item_topic = _normalize_text(str(item.get("topic_hint") or metadata.get("topic_hint") or metadata.get("title") or ""))
            source_filename = str(item.get("source_filename") or metadata.get("filename") or Path(item.get("source_path", "")).name)
            filter_text = " ".join(
                part
                for part in [
                    item.get("content"),
                    item_topic,
                    source_filename,
                    item.get("source_path"),
                ]
                if part
            )
            topic_score = _keyword_score(filter_text, tuple(term.lower() for term in clean_topic_keywords))

            if subject_filters:
                if item_subject:
                    if item_subject not in subject_filters:
                        continue
                elif clean_topic_keywords and topic_score <= 0:
                    continue

            if stage_filters and item_stage and item_stage not in stage_filters:
                continue

            adjusted_score = float(score)
            if subject_filters and item_subject in subject_filters:
                adjusted_score += 2.5
            if stage_filters and item_stage in stage_filters:
                adjusted_score += 1.0
            adjusted_score += topic_score * 0.4

            ranked_hits.append(
                RetrievalHit(
                    chunk_id=item["chunk_id"],
                    asset_id=item.get("asset_id"),
                    content=item["content"],
                    score=adjusted_score,
                    page_label=item.get("page_label"),
                    source_type="knowledge-base",
                    source_title=str(metadata.get("title") or item_topic or source_filename or "") or None,
                    source_path=item.get("source_path"),
                    source_filename=source_filename or None,
                    subject_tag=item_subject,
                    stage_tag=item_stage,
                    topic_hint=item_topic or None,
                )
            )
        ranked_hits.sort(key=lambda hit: hit.score or 0.0, reverse=True)
        return ranked_hits[:search_top_k]
