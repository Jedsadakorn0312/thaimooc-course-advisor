import argparse
import json
from pathlib import Path
from .data import DEFAULT_DB, load_jsonl, save_courses, read_courses, quality_report


def main():
    parser = argparse.ArgumentParser(description="Thai MOOC search and RAG starter")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import"); imp.add_argument("file")
    sub.add_parser("quality")
    search = sub.add_parser("search"); search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--max-hours", type=float); search.add_argument("--level")
    search.add_argument("--rag", action="store_true")
    ev = sub.add_parser("evaluate"); ev.add_argument("file"); ev.add_argument("--k", type=int, default=5)
    crawl = sub.add_parser("collect"); crawl.add_argument("url_file")
    crawl.add_argument("--output", default="data/processed/collected.jsonl")
    crawl.add_argument("--raw-dir", default="data/raw"); crawl.add_argument("--delay", type=float, default=2)
    args = parser.parse_args()
    try:
        if args.command == "import":
            courses = load_jsonl(args.file); save_courses(courses, args.db); result = quality_report(courses)
        elif args.command == "quality":
            result = quality_report(read_courses(args.db))
        elif args.command == "collect":
            from .collector import collect
            result = {"collected": collect(args.url_file, args.output, args.raw_dir, args.delay)}
        else:
            from .search import SearchEngine
            engine = SearchEngine(read_courses(args.db))
            if args.command == "evaluate":
                from .evaluation import evaluate
                result = evaluate(engine, json.loads(Path(args.file).read_text(encoding="utf-8")), args.k)
            else:
                result = engine.search(args.query, top_k=args.top_k, max_hours=args.max_hours, level=args.level)
                if args.rag:
                    from .generation import recommend
                    result = recommend(args.query, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
