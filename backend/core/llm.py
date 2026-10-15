"""The only module that talks to the LLM provider (Gemini). Swap the provider here.

Retries are deliberately not done here: Celery tasks retry on NETWORK_ERRORS instead.
"""

import json
import logging
from functools import lru_cache

from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 100  # Gemini's per-request limit for batch embeddings


class LLMError(Exception):
    """Raised when the model returns something we can't use."""


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set")
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=settings.LLM_TIMEOUT_SECONDS * 1000,  # milliseconds
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def embed_many(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if not texts:
        return []
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        response = _client().models.embed_content(
            model=settings.GEMINI_EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM, task_type=task_type),
        )
        embeddings = response.embeddings or []
        if len(embeddings) != len(batch):
            raise LLMError(f"Expected {len(batch)} embeddings, got {len(embeddings)}")
        vectors.extend(list(e.values) for e in embeddings)
    return vectors


def embed(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    return embed_many([text], task_type=task_type)[0]


def generate(system_prompt: str, user_prompt: str) -> str:
    response = _client().models.generate_content(
        model=settings.GEMINI_CHAT_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2),
    )
    text = (response.text or "").strip()
    if not text:
        raise LLMError("The model returned an empty response")
    return text


def generate_json(system_prompt: str, user_prompt: str) -> dict | list:
    response = _client().models.generate_content(
        model=settings.GEMINI_CHAT_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON from model: %.200s", raw)
        raise LLMError(f"Model did not return valid JSON: {exc}") from exc
