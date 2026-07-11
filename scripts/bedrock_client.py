"""Shared Bedrock client with token budget controls."""

from __future__ import annotations

import os

import boto3
from botocore.config import Config

from utils import env_int


def converse(prompt: str, *, max_tokens: int | None = None) -> str:
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id:
        raise ValueError("BEDROCK_MODEL_ID is not set")

    region = os.environ.get("AWS_REGION", "us-east-1")
    output_limit = max_tokens or env_int("BEDROCK_MAX_OUTPUT_TOKENS", 2048)

    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            retries={"max_attempts": 2, "mode": "adaptive"},
            connect_timeout=30,
            read_timeout=180,
        ),
    )

    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={
            "maxTokens": output_limit,
            # Claude Sonnet 4.5+ accepts only one of temperature/topP
            "temperature": 0.1,
        },
    )

    blocks = response.get("output", {}).get("message", {}).get("content", [])
    texts = [b["text"] for b in blocks if "text" in b]
    if not texts:
        raise RuntimeError(f"Empty Bedrock response: {response}")
    return "\n".join(texts)
