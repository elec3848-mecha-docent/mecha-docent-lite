"""Thin wrapper around ``llama-cpp-python`` for the Medo dialogue engine.

Functions
---------
:func:`load_llama`
    Loads a GGUF model from disk using the runtime arguments produced by
    :func:`~LLM.config.parse_args`.  Exits with a descriptive message if the
    model file is missing or the library is not installed.

:func:`call_json`
    Sends a chat-completion request and parses the response as JSON.  The
    ``response_format={"type": "json_object"}`` constraint is passed to the
    model, but the caller is responsible for validating the returned dict
    against its expected schema.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_llama(args: argparse.Namespace):
    model_path = Path(args.model).expanduser().resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model file not found: {model_path}")

    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise SystemExit(
            "llama-cpp-python is not installed. Run: pip install llama-cpp-python"
        ) from exc

    kwargs = {
        "model_path": str(model_path),
        "n_ctx": args.n_ctx,
        "n_threads": args.n_threads,
        "n_batch": args.n_batch,
        "n_gpu_layers": 0,
        "use_mmap": True,
        "use_mlock": False,
        "verbose": False,
    }
    if args.chat_format:
        kwargs["chat_format"] = args.chat_format

    try:
        return Llama(**kwargs)
    except Exception as exc:
        raise SystemExit(f"Failed to load model: {exc}") from exc


def call_json(llm, messages: list[dict], max_tokens: int, temperature: float) -> dict:
    try:
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise ValueError(f"LLM inference failed: {exc}") from exc

    raw = response["choices"][0]["message"]["content"].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON output: {raw[:200]}") from exc
