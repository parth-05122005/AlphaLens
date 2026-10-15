"""Exception types worth retrying in network/LLM-facing Celery tasks."""

import httpx
from google.genai import errors as genai_errors

NETWORK_ERRORS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    httpx.TransportError,
    genai_errors.ServerError,  # 5xx from Gemini
)
