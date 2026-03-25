from __future__ import annotations

import threading
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory, session

from engine.dialogue_manager import FinancialAssistant
from financial_assistant.config import RESULT_DIR
from financial_assistant.task_runner import build_knowledge, create_db_engine, ensure_database

from .utils import example_questions, normalize_answer_payload, project_overview


_engine = None
_assistants: dict[str, FinancialAssistant] = {}
_rebuild_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        ensure_database(reset_database=False)
        _engine = create_db_engine()
    return _engine


def _session_id() -> str:
    sid = session.get("assistant_sid")
    if not sid:
        sid = uuid.uuid4().hex
        session["assistant_sid"] = sid
    return sid


def _get_assistant() -> FinancialAssistant:
    sid = _session_id()
    assistant = _assistants.get(sid)
    if assistant is None:
        assistant = FinancialAssistant(_get_engine())
        _assistants[sid] = assistant
    return assistant


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent / "static"),
    )
    app.config["SECRET_KEY"] = "big-data-experiment-web"
    app.config["JSON_AS_ASCII"] = False

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/api/overview")
    def overview():
        return jsonify(
            {
                "ok": True,
                "overview": project_overview(),
                "examples": example_questions(),
            }
        )

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"ok": False, "message": "请输入问题内容"}), 400

        assistant = _get_assistant()
        question_id = str(payload.get("question_id") or f"WEB_{_session_id()[:8]}_{uuid.uuid4().hex[:8]}")
        turn_index = len(assistant.history)
        try:
            answer_payload, sqls = assistant.process_query(message, question_id, turn_index)
        except Exception as exc:  # pragma: no cover - runtime guard
            return jsonify({"ok": False, "message": f"问题处理失败: {exc}"}), 500
        return jsonify({"ok": True, **normalize_answer_payload(answer_payload, sqls)})

    @app.post("/api/reset-session")
    def reset_session():
        sid = session.pop("assistant_sid", None)
        if sid:
            _assistants.pop(sid, None)
        return jsonify({"ok": True})

    @app.post("/api/rebuild-db")
    def rebuild_db():
        global _engine
        if _rebuild_lock.locked():
            return jsonify({"ok": False, "message": "数据库正在重建，请稍后再试"}), 409

        with _rebuild_lock:
            ensure_database(reset_database=True)
            _engine = create_db_engine()
            _assistants.clear()
        return jsonify({"ok": True, "overview": project_overview()})

    @app.post("/api/rebuild-knowledge")
    def rebuild_knowledge():
        build_knowledge(force_rebuild=True)
        return jsonify({"ok": True, "overview": project_overview()})

    @app.get("/result/<path:filename>")
    def result_file(filename: str):
        return send_from_directory(str(RESULT_DIR), filename)

    return app


def run_frontend(
    host: str = "127.0.0.1",
    port: int = 7860,
    debug: bool = False,
    open_browser: bool = False,
) -> None:
    ensure_database(reset_database=False)
    app = create_app()
    url = f"http://{host}:{port}"
    print(f"web frontend running at {url}")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=debug)
