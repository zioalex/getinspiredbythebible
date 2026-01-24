#!/bin/bash
# Initialize Ollama with required models

set -e

echo "Starting Ollama service..."
ollama serve &

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
sleep 5

# Pull required models
# Note: In some stacks we use OpenRouter (remote) for chat but still use Ollama for embeddings.
# In that case we should NOT pull the chat model into Ollama.
if [ "${LLM_PROVIDER:-ollama}" = "ollama" ]; then
	echo "Pulling LLM model: ${LLM_MODEL:-llama3:8b}..."
	ollama pull "${LLM_MODEL:-llama3:8b}"
else
	echo "Skipping LLM model pull (LLM_PROVIDER=${LLM_PROVIDER})"
fi

if [ "${EMBEDDING_PROVIDER:-ollama}" = "ollama" ]; then
	echo "Pulling embedding model: ${EMBEDDING_MODEL:-nomic-embed-text}..."
	ollama pull "${EMBEDDING_MODEL:-nomic-embed-text}"
else
	echo "Skipping embedding model pull (EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER})"
fi

echo "Ollama initialization complete!"

# Keep the service running
wait
