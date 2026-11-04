"""The gateway loads the person's private OpenRouter key file into its own environment for the REPLs' narrate
(repl-llm s-7311fa1b): parsed, never sourced; only a private file (yours, mode 600 or 400); the note names the
file and never the value; a key already in the environment wins."""
import os

from loop.gateway import load_key_file


def test_load_key_file(tmp_path):
    f = tmp_path / "openrouter.env"
    env = {"METIS_OPENROUTER_ENV": str(f)}
    assert load_key_file(env) is None and "OPENROUTER_API_KEY" not in env          # no file: nothing
    f.write_text('# the key\nexport OPENROUTER_API_KEY="sk-or-test-1"\n')
    os.chmod(f, 0o644)
    note = load_key_file(env)
    assert note == f"{f} is not private (mode 600 or 400, yours): not read" and "OPENROUTER_API_KEY" not in env
    os.chmod(f, 0o600)
    note = load_key_file(env)
    assert env["OPENROUTER_API_KEY"] == "sk-or-test-1"
    assert note == f"OPENROUTER_API_KEY from {f}" and "sk-or-test-1" not in note
    f.write_text("OPENROUTER_API_KEY=sk-old\nOPENROUTER_API_KEY='sk-or-last'  # rotated\n")
    env = {"METIS_OPENROUTER_ENV": str(f)}
    assert load_key_file(env) and env["OPENROUTER_API_KEY"] == "sk-or-last"          # the last line, unquoted
    env = {"METIS_OPENROUTER_ENV": str(f), "OPENROUTER_API_KEY": "from-env"}
    assert load_key_file(env) is None and env["OPENROUTER_API_KEY"] == "from-env"    # the environment wins
    f.write_text("OTHER=1\n")
    env = {"METIS_OPENROUTER_ENV": str(f)}
    assert load_key_file(env) == f"{f} has no OPENROUTER_API_KEY= line: not read"
    assert "OPENROUTER_API_KEY" not in env


def test_load_key_file_default_path_is_the_home_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    d = tmp_path / ".config/metis"
    d.mkdir(parents=True)
    (d / "openrouter.env").write_text("OPENROUTER_API_KEY=sk-home\n")
    os.chmod(d / "openrouter.env", 0o400)
    env = {}
    assert load_key_file(env) == f"OPENROUTER_API_KEY from {d / 'openrouter.env'}"
    assert env["OPENROUTER_API_KEY"] == "sk-home"
