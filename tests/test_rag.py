from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient
import numpy as np

from app.config import get_settings
from app.main import app
from app.models import ParsedAsset, ResourceType
from app.services.rag import LocalKnowledgeBase, OpenAIEmbeddingProvider


client = TestClient(app)


def _make_project_test_dir(base: Path) -> Path:
    path = base / f"_rag_tests_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class _FakeEmbeddingRecord:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.data = [_FakeEmbeddingRecord(item) for item in embeddings]


class _FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def create(self, *, model: str, input: list[str], dimensions: int | None = None) -> _FakeEmbeddingResponse:
        self.calls.append(list(input))
        width = dimensions or 4
        embeddings = [[float(index + 1)] * width for index, _ in enumerate(input)]
        return _FakeEmbeddingResponse(embeddings)


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()


def test_local_knowledge_base_ingest_and_search_roundtrip() -> None:
    settings = get_settings()
    source_dir = _make_project_test_dir(settings.knowledge_base_dir)
    store_dir = _make_project_test_dir(settings.vector_store_dir)

    try:
        lesson_path = source_dir / "math.txt"
        lesson_path.write_text(
            "一次函数的图像是一条直线，k决定倾斜方向，b决定与y轴的交点。",
            encoding="utf-8",
        )

        kb = LocalKnowledgeBase(store_dir=store_dir, embedding_backend="local")
        stats = kb.ingest_paths([lesson_path], reset=True)
        assert stats["processed_files"] == 1
        assert stats["chunk_count"] >= 1

        hits = kb.search("一次函数图像由什么决定", top_k=3)
        assert hits
        assert "一次函数" in hits[0].content
        assert hits[0].subject_tag == "math"

        reloaded = LocalKnowledgeBase(store_dir=store_dir, embedding_backend="local")
        reloaded_hits = reloaded.search("y轴的交点", top_k=3)
        assert reloaded_hits
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(store_dir, ignore_errors=True)


def test_ingest_parsed_asset_json() -> None:
    settings = get_settings()
    parsed_dir = _make_project_test_dir(settings.parsed_data_dir)
    store_dir = _make_project_test_dir(settings.vector_store_dir)

    try:
        parsed_path = parsed_dir / "asset.json"
        parsed_asset = ParsedAsset(
            resource_type=ResourceType.TEXT,
            source_path="manual-note.txt",
            extracted_text="工业革命推动了生产方式和社会结构的变化。",
            text_preview="工业革命推动变化",
        )
        parsed_path.write_text(
            parsed_asset.model_dump_json(indent=2),
            encoding="utf-8",
        )

        kb = LocalKnowledgeBase(store_dir=store_dir, embedding_backend="local")
        stats = kb.ingest_paths([parsed_path], reset=True)
        assert stats["processed_files"] == 1

        hits = kb.search("工业革命的变化", top_k=3)
        assert hits
        assert "工业革命" in hits[0].content
    finally:
        shutil.rmtree(parsed_dir, ignore_errors=True)
        shutil.rmtree(store_dir, ignore_errors=True)


def test_kb_api_ingest_and_search() -> None:
    settings = get_settings()
    source_dir = _make_project_test_dir(settings.knowledge_base_dir)
    namespace = f"api_test_{uuid4().hex}"

    try:
        (source_dir / "english.txt").write_text(
            "现在完成时用于描述已经发生并对现在仍有影响的动作。",
            encoding="utf-8",
        )

        ingest_response = client.post(
            "/api/kb/ingest",
            json={
                "source_dir": str(source_dir),
                "include_parsed_assets": False,
                "reset": True,
                "store_namespace": namespace,
            },
        )
        assert ingest_response.status_code == 200
        assert ingest_response.json()["stats"]["processed_files"] == 1

        search_response = client.post(
            "/api/kb/search",
            json={
                "query": "现在完成时",
                "top_k": 3,
                "store_namespace": namespace,
            },
        )
        assert search_response.status_code == 200
        payload = search_response.json()
        assert payload["count"] >= 1
        assert "现在完成时" in payload["hits"][0]["content"]
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(settings.vector_store_dir / namespace, ignore_errors=True)


def test_local_knowledge_base_search_supports_subject_filters() -> None:
    settings = get_settings()
    source_dir = _make_project_test_dir(settings.knowledge_base_dir)
    store_dir = _make_project_test_dir(settings.vector_store_dir)

    try:
        history_path = source_dir / "工业革命_历史.txt"
        chemistry_path = source_dir / "化学变化_NaHCO3.txt"
        history_path.write_text(
            "工业革命推动工厂制度形成，并加速了城市化和社会结构变化。",
            encoding="utf-8",
        )
        chemistry_path.write_text(
            "NaHCO3 受热分解会发生化学变化，并生成新的物质。",
            encoding="utf-8",
        )

        kb = LocalKnowledgeBase(store_dir=store_dir, embedding_backend="local")
        kb.ingest_paths([history_path, chemistry_path], reset=True)

        hits = kb.search(
            "变化",
            top_k=5,
            subject_filter=["history"],
            topic_keywords=["工业革命"],
        )
        assert hits
        assert all(hit.subject_tag in {None, "history"} for hit in hits)
        assert "工业革命" in hits[0].content
        assert all("NaHCO3" not in hit.content for hit in hits)
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(store_dir, ignore_errors=True)


def test_kb_api_search_supports_metadata_filters() -> None:
    settings = get_settings()
    source_dir = _make_project_test_dir(settings.knowledge_base_dir)
    namespace = f"api_filter_test_{uuid4().hex}"

    try:
        (source_dir / "工业革命_历史.txt").write_text(
            "工业革命改变了生产方式，也推动了工厂制度和城市化。",
            encoding="utf-8",
        )
        (source_dir / "氯气化学.txt").write_text(
            "氯气与水反应可生成次氯酸，是典型化学知识点。",
            encoding="utf-8",
        )

        ingest_response = client.post(
            "/api/kb/ingest",
            json={
                "source_dir": str(source_dir),
                "reset": True,
                "store_namespace": namespace,
            },
        )
        assert ingest_response.status_code == 200

        search_response = client.post(
            "/api/kb/search",
            json={
                "query": "变化",
                "top_k": 5,
                "store_namespace": namespace,
                "subject_filter": ["history"],
                "topic_keywords": ["工业革命"],
            },
        )
        assert search_response.status_code == 200
        payload = search_response.json()
        assert payload["count"] >= 1
        assert payload["hits"][0]["subject_tag"] == "history"
        assert "工业革命" in payload["hits"][0]["content"]
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(settings.vector_store_dir / namespace, ignore_errors=True)


def test_openai_embedding_provider_batches_requests_for_compatible_gateways() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="test",
        model="text-embedding-v4",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        batch_size=10,
    )
    fake_client = _FakeOpenAIClient()
    provider.client = fake_client  # type: ignore[assignment]

    vectors = provider.embed_texts([f"chunk-{index}" for index in range(25)])

    assert vectors.shape == (25, 4)
    assert [len(call) for call in fake_client.embeddings.calls] == [10, 10, 5]
    assert provider.dimension == 4


def test_openai_backed_reset_rebuild_ignores_previous_store_dimension() -> None:
    settings = get_settings()
    source_dir = _make_project_test_dir(settings.knowledge_base_dir)
    store_dir = _make_project_test_dir(settings.vector_store_dir)

    try:
        seed_path = source_dir / "history.txt"
        seed_path.write_text("工业革命推动了生产组织方式的变化。", encoding="utf-8")

        local_kb = LocalKnowledgeBase(store_dir=store_dir, embedding_backend="local")
        local_kb.ingest_paths([seed_path], reset=True)

        rebuilt_kb = LocalKnowledgeBase(store_dir=store_dir, embedding_backend="local")
        rebuilt_kb.embedding_provider = OpenAIEmbeddingProvider(
            api_key="test",
            model="text-embedding-v4",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            batch_size=10,
        )
        fake_client = _FakeOpenAIClient()
        rebuilt_kb.embedding_provider.client = fake_client  # type: ignore[assignment]
        rebuilt_kb.dimension = None
        rebuilt_kb.index = None
        rebuilt_kb.metadata = []

        stats = rebuilt_kb.ingest_paths([seed_path], reset=True)

        assert stats["processed_files"] == 1
        assert rebuilt_kb.dimension == 4
        assert rebuilt_kb.index is not None
        assert rebuilt_kb.index.d == 4
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(store_dir, ignore_errors=True)


def test_ingest_paths_skips_duplicate_chunk_ids_on_reimport() -> None:
    settings = get_settings()
    source_dir = _make_project_test_dir(settings.knowledge_base_dir)
    store_dir = _make_project_test_dir(settings.vector_store_dir)

    try:
        lesson_path = source_dir / "history_repeat.txt"
        lesson_path.write_text(
            "工业革命推动机器大生产，也推动了工厂制度和城市化。",
            encoding="utf-8",
        )

        kb = LocalKnowledgeBase(store_dir=store_dir, embedding_backend="local")
        first_stats = kb.ingest_paths([lesson_path], reset=True)
        second_stats = kb.ingest_paths([lesson_path], reset=False)

        assert first_stats["processed_files"] == 1
        assert first_stats["chunk_count"] >= 1
        assert second_stats["processed_files"] == 0
        assert second_stats["chunk_count"] == 0
        assert second_stats["total_chunks_in_store"] == first_stats["total_chunks_in_store"]
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(store_dir, ignore_errors=True)
