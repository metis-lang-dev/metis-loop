"""Compatibility shim — the loop kernel moved into metispy
(user decision 2026-10-01: ONE kernel REPL, the metis shell; this
repo is wrappers — web console, Claude Code skill, CLI bindings).
Import metis.loop.llm instead."""
from metis.loop.llm import *          # noqa: F401,F403
