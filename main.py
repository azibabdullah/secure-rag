import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="SecureRAG local application")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Check and index a document")
    ingest.add_argument("file")

    ask = commands.add_parser("ask", help="Ask using approved documents")
    ask.add_argument("question")

    commands.add_parser("gui", help="Open the desktop application")
    commands.add_parser("dashboard", help="Open the web desktop dashboard")
    args = parser.parse_args()

    if args.command == "dashboard":
        from src.gui.web_app import run_dashboard
        raise SystemExit(run_dashboard())

    if args.command == "gui":
        from src.gui.app import run_gui
        raise SystemExit(run_gui())

    from src.rag.pipeline import SecureRAG
    rag = SecureRAG()

    if args.command == "ingest":
        result = rag.ingest(args.file)
    else:
        result = rag.ask(args.question)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()