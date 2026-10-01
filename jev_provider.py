"""Official TypeSafe Jev HTTP adapter; no credentials are written to disk."""
import math
import threading

import httpx

from smart_home import FIELDS

BASE_URL = "https://api.typesafe.ai/v1"
_key = ""
_key_lock = threading.Lock()


class JevError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def configure_key(value):
    global _key
    if not isinstance(value, str):
        raise ValueError("Enter a valid API key.")
    value = value.strip()
    if not 8 <= len(value) <= 512 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError("Enter a valid API key without whitespace.")
    with _key_lock:
        _key = value


def forget_key():
    global _key
    with _key_lock:
        _key = ""


def configured():
    with _key_lock:
        return bool(_key)


def _call(method, path, body=None):
    with _key_lock:
        key = _key
    if not key:
        raise JevError("Enter and save your Jev API key first.", 409)
    try:
        with httpx.Client(timeout=httpx.Timeout(45, connect=10), follow_redirects=False) as client:
            response = client.request(method, BASE_URL + path,
                                      headers={"Authorization": "Bearer " + key}, json=body)
    except httpx.TimeoutException:
        raise JevError("Jev timed out. Retry the request when ready.", 504) from None
    except httpx.HTTPError:
        raise JevError("Could not connect to Jev. Check your internet connection.") from None
    messages = {
        401: ("Jev rejected the API key. Check or replace it.", 401),
        403: ("This Jev key does not have access to the requested resource.", 403),
        402: ("Jev reports insufficient account credit. Check your TypeSafe account.", 402),
        404: ("Jev could not find the requested model or endpoint.", 502),
        422: ("Jev rejected the request format or model. Check the model name.", 422),
        429: ("Jev rate limit reached. Wait before trying again.", 429),
        529: ("Jev is temporarily overloaded. Try again later.", 503),
    }
    if response.status_code != 200:
        message, status = messages.get(response.status_code, ("Jev returned a service error.", 502))
        # Do not forward a provider error body: it can echo request headers or credentials.
        raise JevError(message, status)
    try:
        result = response.json()
    except ValueError:
        raise JevError("Jev returned invalid JSON.") from None
    if not isinstance(result, dict):
        raise JevError("Jev returned an unexpected response.")
    return result


def test_connection():
    result = _call("GET", "/models")
    models = result.get("models")
    if not isinstance(models, list) or any(not isinstance(m, dict) or not isinstance(m.get("name"), str) for m in models):
        raise JevError("Jev returned an unexpected model list.")
    return [m["name"] for m in models]


def _probability(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise JevError("Jev returned an invalid probability.")
    return float(value)


def normalise_response(result):
    """Validate every answer before proposing any device change; retain both certainty measures."""
    answers = result.get("answers")
    if not isinstance(answers, dict):
        raise JevError("Jev did not return the expected switch answers.")
    normalised = {}
    for qid, (_, _, choices) in FIELDS.items():
        answer = answers.get(qid)
        labels = {"keep", *choices}
        if (not isinstance(answer, dict) or answer.get("type") != "choice"
                or not isinstance(answer.get("choice"), str) or answer["choice"] not in labels):
            raise JevError("Jev returned an invalid switch choice.")
        probabilities = answer.get("probabilities")
        if not isinstance(probabilities, dict) or set(probabilities) != labels:
            raise JevError("Jev returned an incomplete switch distribution.")
        probabilities = {label: _probability(value) for label, value in probabilities.items()}
        if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=0.02):
            raise JevError("Jev returned an invalid switch distribution.")
        normalised[qid] = {"type": "choice", "choice": answer["choice"],
                           "probabilities": probabilities, "confidence": _probability(answer.get("confidence")),
                           "answer_confidence": probabilities[answer["choice"]]}
    model = result.get("model")
    if not isinstance(model, str) or not model.startswith("jev-") or len(model) > 100:
        raise JevError("Jev returned an unexpected model identifier.")
    usage = result.get("usage", {})
    return {"model": model, "answers": normalised,
            "usage": {k: v for k, v in usage.items() if k in {"input_tokens", "output_tokens"} and isinstance(v, int) and v >= 0}
            if isinstance(usage, dict) else {}}


def predict(command, questions, model):
    return normalise_response(_call("POST", "/systemone", {"state": command, "questions": questions, "model": model}))
