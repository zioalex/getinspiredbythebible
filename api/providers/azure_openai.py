"""
Azure OpenAI Embedding Provider implementation.
Uses Azure OpenAI Service for generating embeddings.
"""

from openai import AsyncAzureOpenAI

from .base import EmbeddingProvider, EmbeddingResponse


class AzureOpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Embedding Provider for Azure OpenAI Service.

    Uses Azure-hosted OpenAI models like text-embedding-3-small.
    Requires Azure OpenAI resource with deployed embedding model.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment_name: str,
        dimensions: int = 1536,
    ):
        """
        Initialize Azure OpenAI embedding provider.

        Args:
            endpoint: Azure OpenAI resource endpoint (e.g., https://your-resource.openai.azure.com/)
            api_key: Azure OpenAI API key
            deployment_name: Name of the deployed embedding model
            dimensions: Embedding vector dimensions (1536 for text-embedding-3-small)
        """
        self.endpoint = endpoint.rstrip("/")
        self.deployment_name = deployment_name
        self._dimensions = dimensions
        self._client = AsyncAzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=api_key,
            api_version="2024-02-01",
        )

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding for a single text."""
        response = await self._client.embeddings.create(
            input=text,
            model=self.deployment_name,
        )

        return EmbeddingResponse(
            embedding=response.data[0].embedding,
            model=self.deployment_name,
            provider=self.provider_name,
        )

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResponse]:
        """
        Generate embeddings for multiple texts.

        Azure OpenAI supports batch embedding natively, which is more efficient
        than sequential calls.
        """
        # Azure OpenAI has a limit of 2048 texts per batch
        # Process in chunks if needed
        batch_size = 100
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.embeddings.create(
                input=batch,
                model=self.deployment_name,
            )

            for embedding_data in response.data:
                results.append(
                    EmbeddingResponse(
                        embedding=embedding_data.embedding,
                        model=self.deployment_name,
                        provider=self.provider_name,
                    )
                )

        return results

    async def health_check(self) -> bool:
        """Check if the Azure OpenAI embedding service is available."""
        try:
            # Try a simple embedding request
            await self._client.embeddings.create(
                input="health check",
                model=self.deployment_name,
            )
            return True
        except Exception:
            return False

    async def close(self):
        """Close the client (no-op for Azure OpenAI SDK)."""
        # The Azure OpenAI SDK manages its own connection pool
        pass
