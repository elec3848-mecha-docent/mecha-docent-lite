"""MechaDocent LLM demo entry point."""

from __future__ import annotations

import argparse
import os

from LLM.app.orchestrator import run
from LLM.generation.llm_client import load_llama


def run_llm_demo(
    model_path: str = "models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    exhibits_path: str = "exhibits.json",
    output_path: str = "output.json",
    profile_path: str = "profile_current.json",
    silence_timeout: int = 20,
    chat_format: str | None = None,
    n_ctx: int = 2048,
    n_threads: int | None = None,
    n_batch: int = 128,
    max_tokens: int = 300,
    temperature: float = 0.35,
) -> int:
    args = argparse.Namespace(
        model=model_path,
        exhibits=exhibits_path,
        output_path=output_path,
        profile_path=profile_path,
        silence_timeout=silence_timeout,
        chat_format=chat_format,
        n_ctx=n_ctx,
        n_threads=n_threads if n_threads is not None else min(4, os.cpu_count() or 1),
        n_batch=n_batch,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    print("Loading model...", flush=True)
    llm = load_llama(args)
    print("MechaDocent (Medo) is ready.")
    print("Commands: /exit, /quit, quit\n")
    return run(args, llm)
