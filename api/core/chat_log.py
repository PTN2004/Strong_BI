"""Ghi log server-side mỗi thread hỏi-đáp — phục vụ admin trace khi sale báo lỗi.

ThreadCapture gom event từ stream v4 (TRƯỚC khi lọc theo ui_permissions) và ghi
1 row `chat_threads` khi stream kết thúc. Ghi log lỗi không được phép làm hỏng
response cho user — mọi exception khi save chỉ log warning.
"""
import asyncio
import logging
import re
import time
import uuid as uuid_lib

MAX_ROWS = 200
MAX_STEPS = 60
_ID_RE = re.compile(r"^[A-Za-z0-9\-_]{6,64}$")


class ThreadCapture:
    def __init__(self, thread_id, user_id: str, user_email: str, graph_id: str, query: str):
        self.id = thread_id if (thread_id and _ID_RE.match(thread_id)) else str(uuid_lib.uuid4())
        self.user_id = user_id
        self.user_email = user_email
        self.graph_id = graph_id
        self.query = query[:4000]
        self.t0 = time.perf_counter()
        self.steps: list[str] = []
        self.sql = None
        self.answer = None
        self.error = None
        self.table_data = None
        self.chart_config = None
        self.playbook = None
        self.intent = None
        
        # Metrics Tracking
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.cost_usd = 0.0
        self.api_calls_count = 0
        self.engine_version = "v4" # Default, updated if v5 or explicitly set
        
        self._saved = False

    def record(self, event: dict) -> None:
        try:
            etype = event.get("type")
            if etype == "reasoning_step":
                msg = (event.get("message") or "")[:500]
                if len(self.steps) < MAX_STEPS:
                    self.steps.append(msg)
                low = msg.lower()
                if "playbook" in low and "kích hoạt" in low:
                    self.intent = "playbook"
                    m = re.search(r"'([^']+)'", msg)
                    if m:
                        self.playbook = m.group(1)[:64]
            elif etype == "sql_query":
                self.sql = str(event.get("data") or "")[:8000]
                self.intent = self.intent or "data_query"
            elif etype == "query_result":
                data = event.get("data")
                if isinstance(data, list):
                    self.table_data = data[:MAX_ROWS]
            elif etype == "chart_config":
                self.chart_config = {"option": event.get("data"),
                                     "chart_type": event.get("chart_type")}
            elif etype == "ai_response" and event.get("final_response"):
                self.answer = (event.get("message") or "")[:16000]
                if self.intent is None:
                    self.intent = "direct_reply"  # greeting / out_of_scope
            elif etype == "metrics":
                data = event.get("data", {})
                self.prompt_tokens = data.get("prompt_tokens", 0)
                self.completion_tokens = data.get("completion_tokens", 0)
                self.total_tokens = data.get("total_tokens", 0)
                self.cost_usd = data.get("cost_usd", 0.0)
                self.api_calls_count = data.get("api_calls_count", 0)
                if "engine_version" in data:
                    self.engine_version = data.get("engine_version")
            elif etype == "error":
                self.error = (event.get("message") or event.get("content") or "")[:4000]
        except Exception:
            pass  # capture không được làm hỏng stream

    async def save(self) -> None:
        if self._saved:
            return
        self._saved = True
        try:
            await asyncio.to_thread(self._save_sync)
        except Exception as e:
            logging.warning("chat_log save failed (thread %s): %s", self.id, e)

    def _save_sync(self) -> None:
        import json as _json

        from api.auth.models import ChatThread
        from api.database import get_session_factory

        db = get_session_factory()()
        try:
            def _safe(o):
                return _json.loads(_json.dumps(o, default=str)) if o is not None else None

            row = db.get(ChatThread, self.id)
            if row is None:
                row = ChatThread(id=self.id, user_id=self.user_id,
                                 user_email=self.user_email, graph_id=self.graph_id,
                                 query=self.query)
                db.add(row)
            row.status = "error" if self.error else "done"
            row.intent = self.intent
            row.playbook = self.playbook
            row.sql = self.sql
            row.answer = self.answer
            row.error = self.error
            row.steps = self.steps or None
            row.table_data = _safe(self.table_data)
            row.chart_config = _safe(self.chart_config)
            row.duration_ms = int((time.perf_counter() - self.t0) * 1000)
            
            # Save metrics
            row.prompt_tokens = self.prompt_tokens
            row.completion_tokens = self.completion_tokens
            row.total_tokens = self.total_tokens
            row.cost_usd = self.cost_usd
            row.api_calls_count = self.api_calls_count
            row.engine_version = self.engine_version
            
            db.commit()
        finally:
            db.close()
