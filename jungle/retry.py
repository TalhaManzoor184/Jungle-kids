import re
import time


def _status(err) -> int | None:
    for attr in ("code", "status_code", "status"):
        v = getattr(err, attr, None)
        if isinstance(v, int):
            return v
    return None


def is_transient(err) -> bool:
    """Errors that usually clear on their own: overload, server errors, network blips, per-minute limits."""
    s = _status(err)
    if s in (500, 502, 503, 504):
        return True
    msg = str(err)
    if re.search(r"\b(503|UNAVAILABLE|high demand|overloaded|ECONNRESET|timed out|Connection reset)\b", msg, re.I):
        return True
    if (s == 429 or re.search(r"\b429\b", msg)) and not re.search(r"per day|requests per day|retry in \d+h", msg, re.I):
        return True
    return False


def is_quota(err) -> bool:
    return _status(err) == 429 or bool(re.search(r"\b429\b|RESOURCE_EXHAUSTED|quota|rate limit", str(err), re.I))


def should_fall_back(err) -> bool:
    return is_transient(err) or is_quota(err)


def with_retry(label: str, fn, tries: int = 5):
    """Retry fn on transient errors with backoff 15 s, 30 s, 60 s, 120 s."""
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as err:  # noqa: BLE001
            if attempt >= tries or not is_transient(err):
                raise
            wait = 15 * 2 ** (attempt - 1)
            print(f"  {label}: {str(err)[:160]} - retrying in {wait}s")
            time.sleep(wait)


def with_fallback(label: str, models: list[str], fn):
    """Call fn(model) with retries; move to the next model when one is busy or out of quota."""
    models = [m for m in models if m]
    for i, model in enumerate(models):
        try:
            return with_retry(f"{label} ({model})", lambda: fn(model))
        except Exception as err:  # noqa: BLE001
            if i == len(models) - 1 or not should_fall_back(err):
                raise
            print(f"  {model} is busy or out of quota; trying {models[i + 1]}")
