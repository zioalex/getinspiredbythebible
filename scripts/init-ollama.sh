#!/bin/bash
# Initialize Ollama with required models

set -e

echo "Starting Ollama service..."
ollama serve &

# Wait for Ollama to be ready (poll until it responds)
echo "Waiting for Ollama to start..."
max_attempts=30
attempt=0
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "ERROR: Ollama failed to start after ${max_attempts} attempts"
        exit 1
    fi
    echo "  Waiting for Ollama... (attempt $attempt/$max_attempts)"
    sleep 2
done
echo "Ollama is ready!"

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
	echo "Pulling embedding model: ${EMBEDDING_MODEL:-mxbai-embed-large}..."
	ollama pull "${EMBEDDING_MODEL:-mxbai-embed-large}"
else
	echo "Skipping embedding model pull (EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER})"
fi

echo "Ollama initialization complete!"

# Keep the service running
wait
