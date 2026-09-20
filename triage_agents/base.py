"""Groq + OpenAI Agents SDK setup.

This package is named `triage_agents` so it does not shadow the SDK package
`agents` (`from agents import Agent`).
"""
from __future__ import annotations

import os

from agents import set_default_openai_api, set_default_openai_client
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def configure_groq_client() -> AsyncOpenAI:
    """Point the Agents SDK at Groq's OpenAI-compatible Chat Completions API."""
    client = AsyncOpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )
    set_default_openai_client(client)
    set_default_openai_api("chat_completions")
    return client
