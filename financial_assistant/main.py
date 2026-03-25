from __future__ import annotations

import argparse
import json

from frontend.app import run_frontend

from .task_runner import (
    answer_single_question,
    build_knowledge,
    ensure_database,
    process_single_pdf,
    run_task2,
    run_task3,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="上市公司财报智能问数助手运行入口")
    parser.add_argument(
        "--mode",
        default="all",
        choices=["init", "parse", "task2", "task3", "all", "query", "web", "knowledge"],
    )
    parser.add_argument("--file", help="单个 PDF 路径，用于 parse 模式")
    parser.add_argument("--question", help="单条自然语言问题，用于 query 模式")
    parser.add_argument("--reset-database", action="store_true")
    parser.add_argument("--rebuild-knowledge", action="store_true")
    parser.add_argument("--host", default="127.0.0.1", help="web 模式监听地址")
    parser.add_argument("--port", type=int, default=7860, help="web 模式端口")
    parser.add_argument("--debug", action="store_true", help="启用 Flask 调试模式")
    parser.add_argument("--open-browser", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args()

    if args.mode == "init":
        db_path = ensure_database(reset_database=args.reset_database)
        print(db_path)
    elif args.mode == "parse":
        if args.file:
            print(process_single_pdf(args.file, reset_database=args.reset_database))
        else:
            print(ensure_database(reset_database=True))
    elif args.mode == "task2":
        print(run_task2(reset_database=args.reset_database))
    elif args.mode == "task3":
        print(run_task3(reset_database=args.reset_database, rebuild_knowledge=True))
    elif args.mode == "knowledge":
        build_knowledge(force_rebuild=args.rebuild_knowledge)
        print("knowledge_index_built")
    elif args.mode == "query":
        if not args.question:
            raise SystemExit("请使用 --question 提供自然语言问题")
        result = answer_single_question(args.question)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.mode == "web":
        run_frontend(
            host=args.host,
            port=args.port,
            debug=args.debug,
            open_browser=args.open_browser,
        )
    elif args.mode == "all":
        task2_path = run_task2(reset_database=args.reset_database)
        task3_path = run_task3(reset_database=False, rebuild_knowledge=True)
        print(task2_path)
        print(task3_path)


if __name__ == "__main__":
    main()
