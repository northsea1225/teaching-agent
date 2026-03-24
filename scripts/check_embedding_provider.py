from __future__ import annotations

from app.config import get_settings
from app.services.rag import OpenAIEmbeddingProvider


def main() -> None:
    settings = get_settings()
    if settings.embeddings_backend.strip().lower() != "openai":
        raise SystemExit("EMBEDDINGS_BACKEND is not set to openai")
    if not settings.embeddings_api_key:
        raise SystemExit("EMBEDDINGS_API_KEY is not configured")

    provider = OpenAIEmbeddingProvider(
        api_key=settings.embeddings_api_key,
        model=settings.embeddings_model,
        base_url=settings.embeddings_base_url or None,
        dimensions=settings.embeddings_dimensions,
    )
    vectors = provider.embed_texts(
        [
            "工业革命推动蒸汽机和工厂制度发展。",
            "蒸汽机提升了生产效率，并改变了劳动组织。",
        ]
    )
    print(f"backend={provider.name}")
    print(f"shape={vectors.shape}")
    print(f"dim={provider.dimension}")


if __name__ == "__main__":
    main()
