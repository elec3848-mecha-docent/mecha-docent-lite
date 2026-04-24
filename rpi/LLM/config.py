"""LLM runtime configuration and CLI argument parser.

Provides :func:`parse_args` which returns an :class:`argparse.Namespace` with
all tuneable parameters for the MechaDocent (Medo) dialogue engine.  Every
field has a sensible default so the system runs without any flags; command-line
overrides are available for model path, inference parameters, file paths, and
conversation timeouts.

Default values
--------------
* Model  : ``models/qwen2.5-1.5b-instruct-q4_k_m.gguf``
* Context: 2048 tokens
* Threads: min(4, cpu_count)
* Temperature: 0.35
"""
from __future__ import annotations

import argparse
import os


DEFAULT_MODEL = "models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEFAULT_EXHIBITS = "exhibits.json"
DEFAULT_OUTPUT_PATH = "output.json"
DEFAULT_PROFILE_PATH = "profile_current.json"
DEFAULT_SILENCE_TIMEOUT = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MechaDocent (Medo) modular runtime")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Path to GGUF model file")
    parser.add_argument("--exhibits", default=DEFAULT_EXHIBITS, help="Path to exhibits JSON")
    parser.add_argument("--output-path", default=DEFAULT_OUTPUT_PATH, help="Path to runtime packet JSON")
    parser.add_argument(
        "--profile-path",
        default=DEFAULT_PROFILE_PATH,
        help="Path to the current-session profile JSON (overwritten each run)",
    )
    parser.add_argument(
        "--silence-timeout",
        type=int,
        default=DEFAULT_SILENCE_TIMEOUT,
        help="Seconds before silence is treated as potential disengagement",
    )
    parser.add_argument("--chat-format", default=None, help="Optional explicit chat format")
    parser.add_argument("--n-ctx", type=int, default=2048)
    parser.add_argument("--n-threads", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--n-batch", type=int, default=128)
    parser.add_argument("--max-tokens", type=int, default=300)
    parser.add_argument("--temperature", type=float, default=0.35)
    return parser.parse_args()
