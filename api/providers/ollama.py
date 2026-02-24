"""
Ollama LLM Provider implementation.
Connects to a local or remote Ollama instance.
"""

import json
import time
from typing import AsyncIterator

import httpx

from middleware.context import REQUEST_ID_CTX_VAR
from utils.telemetry import llm_duration_histogram, llm_tracer, llm_ttft_histogram

from .base import (
    ChatMessage,
    EmbeddingProvider,
    EmbeddingResponse,
    LLMProvider,
    LLMResponse,
)


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
        kwargs.pop("model_override", None)  # Not supported, ignore
        client = await self._get_client()

        start_time = time.perf_counter()
        with llm_tracer.start_as_current_span("llm.ollama.chat") as span:
            span.set_attribute("llm.provider", self.provider_name)
            span.set_attribute("llm.model", self.model)
            span.set_attribute("llm.streaming", False)
            request_id = REQUEST_ID_CTX_VAR.get("")
            if request_id:
                span.set_attribute("request_id", request_id)

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

            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("llm.duration_ms", duration_ms)

            llm_duration_histogram.record(
                duration_ms,
                {"provider": self.provider_name, "model": self.model, "streaming": "false"},
            )

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
        kwargs.pop("model_override", None)  # Not supported, ignore
        client = await self._get_client()

        span = llm_tracer.start_span("llm.ollama.chat_stream")
        start_time = time.perf_counter()
        first_token_time: float | None = None

        try:
            span.set_attribute("llm.provider", self.provider_name)
            span.set_attribute("llm.model", self.model)
            span.set_attribute("llm.streaming", True)
            request_id = REQUEST_ID_CTX_VAR.get("")
            if request_id:
                span.set_attribute("request_id", request_id)

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
                            if first_token_time is None and data["message"]["content"]:
                                first_token_time = time.perf_counter()
                            yield data["message"]["content"]
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("llm.duration_ms", duration_ms)

            if first_token_time is not None:
                ttft_ms = (first_token_time - start_time) * 1000
                span.set_attribute("llm.ttft_ms", ttft_ms)
                llm_ttft_histogram.record(
                    ttft_ms, {"provider": self.provider_name, "model": self.model}
                )

            llm_duration_histogram.record(
                duration_ms,
                {"provider": self.provider_name, "model": self.model, "streaming": "true"},
            )
            span.end()

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
