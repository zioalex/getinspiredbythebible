#!/bin/bash
# Initialize Ollama with required models

set -e

echo "Starting Ollama service..."
ollama serve &

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
sleep 5

# Pull required models
echo "Pulling LLM model: ${LLM_MODEL:-llama3:8b}..."
ollama pull "${LLM_MODEL:-llama3:8b}"

echo "Pulling embedding model: ${EMBEDDING_MODEL:-nomic-embed-text}..."
ollama pull "${EMBEDDING_MODEL:-nomic-embed-text}"

echo "Ollama initialization complete!"

# Keep the service running
wait
