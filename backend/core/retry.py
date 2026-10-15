"""Exception types worth retrying in network/LLM-facing Celery tasks."""

NETWORK_ERRORS: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)
