"""Run the upstream playground on loopback using workspace-local cached models."""
import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(ROOT / ".cache" / "huggingface")
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["LAYA_REVISION"] = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch

torch.set_num_threads(4)
runpy.run_path(str(ROOT / "laya" / "examples" / "server.py"), run_name="__main__")
