"""Write loop/chat_tools.json, the chat's /commands as declared tools, FROM their argparse (loop/chat.py parser();
loop-chat s-f6c32d0c step 2, docs/CHAT.md §2), the way metispy's tools/gen_trace_tools.py writes trace_tools.json:
the backend answers exactly these, /help reads them.

    python tools/gen_chat_tools.py           # rewrite the file
    python tools/gen_chat_tools.py --check   # exit 1 when the file is not what the commands declare
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.chat import TOOLS_FILE, tools_json  # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    want = tools_json()
    if "--check" in argv:
        have = TOOLS_FILE.read_text() if TOOLS_FILE.is_file() else ""
        if have != want:
            print("%s is not what the commands declare: python tools/gen_chat_tools.py" % TOOLS_FILE, file=sys.stderr)
            return 1
        print("%s: as the commands declare" % TOOLS_FILE.name)
        return 0
    TOOLS_FILE.write_text(want)
    print("wrote %s (%d commands)" % (TOOLS_FILE, want.count('"name": ')))
    return 0


if __name__ == "__main__":
    sys.exit(main())
