"""Loopback smart-home simulator: hosted Jev or local Laya. No hardware integrations."""
import argparse
import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(ROOT / ".cache" / "huggingface")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from laya import Router
from smart_home import DEFAULT_STATE, jev_questions, project_answers, questions, validate_state
import jev_provider

torch.set_num_threads(4)
router = Router(device="cpu", max_loaded=2, revision=REVISION)
lock = threading.Lock()
app = FastAPI(title="Smart Home Lab — Jev and Laya")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


@app.middleware("http")
async def local_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method in {"POST", "DELETE"} and origin and origin != str(request.base_url).rstrip("/"):
        return JSONResponse({"detail": "Use the local Smart Home Lab page."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class PredictRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)
    state: dict
    provider: Literal["jev", "laya"] = "jev"
    model: Literal["auto", "english", "multilingual"] = "auto"
    jev_model: str = Field(default="jev-latest", pattern=r"^jev-[a-zA-Z0-9._-]{1,80}$")
    prompt_profile: Literal["scoped", "original"] = "scoped"
    threshold: float = Field(default=0.75, ge=0, le=1)


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "device": "cpu", "laya_offline": True, "revision": REVISION,
            "jev_key_configured": jev_provider.configured(),
            "loaded_models": router.loaded, "threads": torch.get_num_threads()}


@app.get("/api/jev/config")
def jev_config():
    return {"configured": jev_provider.configured(), "endpoint": jev_provider.BASE_URL,
            "default_model": "jev-latest"}


@app.post("/api/jev/key")
async def save_jev_key(request: Request):
    # Manual validation avoids reflecting a secret through Pydantic's input error details.
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError()
        jev_provider.configure_key(body.get("api_key"))
    except (ValueError, TypeError):
        raise HTTPException(422, "Enter a valid API key without whitespace.") from None
    return {"configured": True, "storage": "server memory; the browser retains the saved key and restores it after restart"}


@app.delete("/api/jev/key")
def forget_jev_key():
    jev_provider.forget_key()
    return {"configured": False}


@app.post("/api/jev/test")
def test_jev():
    try:
        return {"connected": True, "models": jev_provider.test_connection()}
    except jev_provider.JevError as exc:
        raise HTTPException(exc.status, str(exc)) from None


@app.get("/api/schema")
def schema(provider: Literal["jev", "laya"] = "jev",
           prompt_profile: Literal["scoped", "original"] = "scoped"):
    return {"default_state": DEFAULT_STATE,
            "questions": jev_questions(prompt_profile) if provider == "jev" else questions(),
            "prompt_profile": prompt_profile if provider == "jev" else "original"}


@app.post("/api/predict")
def predict(req: PredictRequest):
    if not req.command.strip():
        raise HTTPException(422, "Enter a command.")
    try:
        validate_state(req.state)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if not lock.acquire(blocking=False):
        raise HTTPException(503, "Another request is running. Try again when it finishes.")
    try:
        started = time.perf_counter()
        if req.provider == "jev":
            result = jev_provider.predict(req.command, jev_questions(req.prompt_profile), req.jev_model)
            route = {"model": result["model"],
                     "reason": f"TypeSafe Jev API · {req.prompt_profile} prompts · one request for eight switches"}
        else:
            route = router.route(req.command, model=None if req.model == "auto" else req.model)
            result = router.predict(req.command, questions(),
                                    model=route["model"], min_confidence=req.threshold)
        projection = project_answers(req.state, result["answers"], req.threshold)
        return {**projection, "command": req.command, "state_before": req.state,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "provider": req.provider, "prompt_profile": req.prompt_profile if req.provider == "jev" else "original",
                "routing": route, "raw": result, "threshold": req.threshold}
    except jev_provider.JevError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logging.exception("Smart home inference failed")
        raise HTTPException(500, "Model failed. Check logs/server.stderr.log.") from exc
    finally:
        lock.release()


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
