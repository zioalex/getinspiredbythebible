"""
Ollama LLM Provider implementation.
Connects to a local or remote Ollama instance.
"""

import json
from typing import AsyncIterator

import httpx

from .base import ChatMessage, EmbeddingProvider, EmbeddingResponse, LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    """
    LLM Provider for Ollama.

    Ollama runs locally and provides access to various open-source models
    like Llama 3, Mistral, Phi-3, etc.
    """

    def __init__(self, host: str, model: str):
        """
        Initialize Ollama provider.

        Args:
            host: Ollama server URL (e.g., http://localhost:11434)
            model: Model name (e.g., llama3:8b, mistral:7b)
        """
        self.host = host.rstrip("/")
        self.model = model
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            # 5 minute timeout to handle cold starts and complex queries
            self._client = httpx.AsyncClient(timeout=300.0)
        return self._client

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to Ollama."""
        client = await self._get_client()

        response = await client.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [msg.model_dump() for msg in messages],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=self.model,
            provider=self.provider_name,
            tokens_used=data.get("eval_count"),
            finish_reason=data.get("done_reason", "stop"),
        )

    async def chat_stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion from Ollama."""
        client = await self._get_client()

        async with client.stream(
            "POST",
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [msg.model_dump() for msg in messages],
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]

    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.host}/api/tags")
            response.raise_for_status()

            # Check if our model is available
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]

            # Model name might be with or without tag
            model_base = self.model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class OllamaEmbeddingProvider(EmbeddingProvider):
    """
    Embedding Provider for Ollama.

    Uses Ollama's embedding endpoint with models like nomic-embed-text.
    """

    def __init__(self, host: str, model: str, dimensions: int = 768):
        """
        Initialize Ollama embedding provider.

        Args:
            host: Ollama server URL
            model: Embedding model name (e.g., nomic-embed-text)
            dimensions: Embedding vector dimensions
        """
        self.host = host.rstrip("/")
        self.model = model
        self._dimensions = dimensions
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding for a single text."""
        client = await self._get_client()

        response = await client.post(
            f"{self.host}/api/embeddings", json={"model": self.model, "prompt": text}
        )
        response.raise_for_status()
        data = response.json()

        return EmbeddingResponse(
            embedding=data["embedding"], model=self.model, provider=self.provider_name
        )

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResponse]:
        """Generate embeddings for multiple texts."""
        # Ollama doesn't have native batch support, so we do it sequentially
        # Could be parallelized with asyncio.gather for better performance
        results = []
        for text in texts:
            result = await self.embed(text)
            results.append(result)
        return results

    async def health_check(self) -> bool:
        """Check if embedding model is available."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.host}/api/tags")
            response.raise_for_status()

            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            model_base = self.model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
