#!/usr/bin/env bash
# Probe NVIDIA API Catalog embeddings with different payload shapes.
# Diagnoses whether a key is valid and what the endpoint requires.
# Usage: ./nvidia-embed-test.sh <NVIDIA_API_KEY> [model]
set -u
KEY="${1:?usage: $0 <NVIDIA_API_KEY> [model]}"
MODEL="${2:-nvidia/llama-nemotron-embed-vl-1b-v2}"
URL="https://integrate.api.nvidia.com/v1/embeddings"

for body in \
  "{\"model\":\"$MODEL\",\"input\":[\"test\"],\"input_type\":\"query\"}" \
  "{\"model\":\"$MODEL\",\"input\":[\"test\"],\"input_type\":\"passage\"}" \
  "{\"model\":\"$MODEL\",\"input\":\"test\"}" \
  "{\"model\":\"$MODEL\",\"input\":[\"test\"]}"; do
  echo "--- $body"
  curl -s --max-time 20 "$URL" \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "$body" -w "\nHTTP %{http_code}\n" | head -c 300
  echo
done

echo
echo "Reading: HTTP 200 + embedding array = key OK and shape OK."
echo "        400 '\''input_type'\'' required = asymmetric model; add it."
echo "        401 = bad key."
