"""Download only the two demo checkpoints at a fixed Hub revision."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(ROOT / ".cache" / "huggingface")
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from huggingface_hub import snapshot_download

REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
patterns = []
for prefix in ("", "multilingual/"):
    patterns.extend(prefix + name for name in (
        "rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*",
    ))
snapshot = snapshot_download("convaiinnovations/laya", revision=REVISION,
                             allow_patterns=patterns, max_workers=2)
manifest = {"repository": "convaiinnovations/laya", "revision": REVISION,
            "snapshot": Path(snapshot).relative_to(ROOT).as_posix(), "cached_models": ["english", "multilingual"]}
(ROOT / "model-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest, indent=2))
