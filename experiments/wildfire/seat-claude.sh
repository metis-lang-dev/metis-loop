#!/bin/sh
# The formalize seat: claude -p as a pure completion (no tools, no MCP, no
# settings, nothing persisted), run from a NEUTRAL cwd — inside a terminal,
# started from the experiment's git checkout, claude -p hung (measured
# 2026-10-09); the seat needs no cwd (the whole prompt is on stdin).
cd /tmp/claude-1000/metis-seat && exec claude -p --tools "" --strict-mcp-config --setting-sources "" --no-session-persistence --model claude-opus-5-5
