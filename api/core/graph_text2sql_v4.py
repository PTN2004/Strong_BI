import asyncio
import json
import logging
import re
import time
import traceback
from typing import Any, AsyncGenerator, Optional, TypedDict, Union
from langgraph.graph import StateGraph, START, END
from datetime import datetime
import sqlglot

from api.core.errors import InternalError
from api.core.pipeline import (
    auto_quote_sql_identifiers,
    detect_destructive_operation,
    get_database_type_and_loader,
    graph_name,
    is_general_graph,
    validate_and_truncate_chat,
    validate_custom_model,
)
from api.core.retriever_v4 import RetrieverV4
from api.agents.insight_and_chart_agent import InsightAndChartAgent
from api.core.text2sql import _build_query_result, _Final
from api.agents.utils import run_completion

logger = logging.getLogger(__name__)

MESSAGE_DELIMITER = "\n\n"

class AgentState(TypedDict):
    workspace_id: str
    user_id: str
    graph_id: str
    chat_data: Any
    db: Any
    custom_api_key: str | None
    custom_model: str | None
    custom_api_base: str | None
    instructions: str | None
    security_filters: dict | None
    
    # Context
    queries_history: list[str]
    db_description: str
    db_url: str
    db_type: str
    loader_class: Any
    graph_context: str
    business_context: str | None
    start_time: float
    
    # Control flow & results
    intent: str | None
    direct_reply: str | None
    playbook: dict | None
    sql_query: str
    validation_error: str | None
    validation_attempts: int
    is_destructive: bool
    
    query_results: list
    execution_error: str | None
    
    insight: str | None
    chart_config: dict | None
    final_answer: str | None
    events_to_yield: list[dict]
    
    # Token Tracking
    total_prompt_tokens: int
    total_completion_tokens: int
    api_calls_count: int

async def init_state(state: AgentState) -> dict:
    start_time = time.perf_counter()
    chat_data = state["chat_data"]
    workspace_id = state["workspace_id"]
    user_id = state["user_id"]
    graph_id = state["graph_id"]
    db = state["db"]
    
    queries_history, _, instructions, _ = validate_and_truncate_chat(chat_data)
    custom_api_key = getattr(chat_data, "custom_api_key", None)
    custom_model = getattr(chat_data, "custom_model", None)
    custom_api_base = getattr(chat_data, "custom_api_base", None)
    security_filters = getattr(chat_data, "security_filters", None)
    validate_custom_model(custom_model)
    
    # Quick DB resolution (using dummy description as graph context replaces it)
    from api.retriever import Retriever
    retriever_v2 = Retriever(graph_id, db)
    db_desc, db_url = await retriever_v2.get_db_description()
    db_type, loader_class = get_database_type_and_loader(db_url)
        
    # Fetch Workspace Business Context
    business_context = None
    try:
        from api.database import get_session_factory
        from api.auth.models import Workspace
        import uuid
        
        _db = get_session_factory()()
        try:
            ws = _db.query(Workspace).filter(Workspace.id == uuid.UUID(workspace_id)).first()
            if ws and (ws.industry or ws.business_goals or ws.kpi_focus):
                business_context = f"Industry: {ws.industry or 'N/A'}\n"
                business_context += f"Business Goals: {ws.business_goals or 'N/A'}\n"
                business_context += f"KPI Focus: {ws.kpi_focus or 'N/A'}"
        finally:
            _db.close()
    except Exception as e:
        logger.warning(f"Failed to fetch workspace context: {e}")

    return {
        "start_time": start_time,
        "queries_history": queries_history,
        "instructions": instructions,
        "security_filters": security_filters,
        "custom_api_key": custom_api_key,
        "custom_model": custom_model,
        "custom_api_base": custom_api_base,
        "db_description": db_desc,
        "db_url": db_url,
        "db_type": db_type,
        "loader_class": loader_class,
        "business_context": business_context,
        "validation_attempts": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "api_calls_count": 0,
        "events_to_yield": [{
            "type": "reasoning_step",
            "final_response": False,
            "message": "Bước 1: Phân tích câu hỏi và thu thập ngữ nghĩa (Semantic GraphRAG)...",
        }]
    }

async def retrieve_schema(state: AgentState) -> dict:
    retriever = RetrieverV4(state["graph_id"], state["db"])
    question = state["queries_history"][-1]
    
    graph_context, graph_data = await retriever.find_context(question)
    
    # Fallback to raw database schema if semantic layer is missing or empty
    if not graph_context or graph_context == "No context found.":
        graph_context = f"Raw Database Schema (No Semantic Layer found):\n{state.get('db_description', 'No schema available.')}"
    
    events = [
        {"type": "reasoning_step", "final_response": False, "message": "Bước 2: Phân tích Cấu trúc Đồ thị (Graph Lineage)..."},
        {"type": "reasoning_graph", "final_response": False, "data": graph_data},
        {"type": "reasoning_step", "final_response": False, "message": "Bước 3: Sinh SQL dựa trên Ngữ nghĩa Kinh doanh..."}
    ]
    
    return {"graph_context": graph_context, "events_to_yield": events}

# ─────────────────────────────────────────────────────────────────────
# Playbook layer (Phase 2) — CHỈ chạy khi PLAYBOOK_ENABLED=true trong .env.
# Tắt flag = pipeline giữ nguyên 100% flow cũ. Xem docs/SALES-PLAYBOOK-DESIGN.md.
# ─────────────────────────────────────────────────────────────────────
import os as _os
from pathlib import Path as _Path

_PLAYBOOKS_DIR = _Path(__file__).resolve().parents[2] / "playbooks"
_playbook_cache: list | None = None
_domain_hints_cache: str | None = None


_scope_limits_cache: dict | None = None


def _scope_gate_text() -> str:
    """Feature flag SCOPE_LIMIT (vd 'S01,S02'): giới hạn nhóm nghiệp vụ được phép.
    Trả về đoạn prompt gate cho classifier; chuỗi rỗng = không giới hạn."""
    allowed = [s.strip().upper() for s in _os.getenv("SCOPE_LIMIT", "").split(",") if s.strip()]
    if not allowed:
        return ""
    global _scope_limits_cache
    if _scope_limits_cache is None:
        try:
            import yaml
            _scope_limits_cache = yaml.safe_load(
                (_PLAYBOOKS_DIR / "scope_limits.yaml").read_text(encoding="utf-8")) or {}
        except Exception:
            _scope_limits_cache = {}
    if not _scope_limits_cache:
        return ""
    ok = "\n".join(f"- {k}: {_scope_limits_cache[k]}" for k in allowed if k in _scope_limits_cache)
    blocked = "\n".join(f"- {k}: {v}" for k, v in _scope_limits_cache.items() if k not in allowed)
    return (f"\n### GIỚI HẠN PHẠM VI PHIÊN BẢN HIỆN TẠI (feature flag):\n"
            f"CHỈ các nhóm sau được phép trả lời bằng dữ liệu:\n{ok}\n"
            f"Các nhóm sau ĐANG PHÁT TRIỂN — nếu câu hỏi thuộc nhóm này thì intent phải là "
            f"\"out_of_scope\" và reply: nói lịch sự rằng nội dung thuộc phạm vi đang được "
            f"phát triển, sẽ có ở phiên bản sau, kèm gợi ý những gì ĐANG hỗ trợ (doanh thu, "
            f"đơn hàng, cửa hàng):\n{blocked}\n"
            f"Chú ý các ghi chú '(Lưu ý: ... thuộc S01 — được phép)' để không chặn nhầm.\n")


def _load_domain_hints() -> str:
    """playbooks/domain_hints.md — tri thức domain nạp vào prompt sinh SQL
    (mapping miền→tỉnh, cách join kênh, shop=customer...). Không có file = chuỗi rỗng."""
    global _domain_hints_cache
    if _domain_hints_cache is None:
        try:
            _domain_hints_cache = (_PLAYBOOKS_DIR / "domain_hints.md").read_text(encoding="utf-8")
        except Exception:
            _domain_hints_cache = ""
    return _domain_hints_cache


def _playbook_enabled() -> bool:
    return False


def _load_playbooks() -> list:
    global _playbook_cache
    if _playbook_cache is not None:
        return _playbook_cache
    playbooks = []
    try:
        import yaml
        for f in sorted(_PLAYBOOKS_DIR.glob("*.yaml")):
            try:
                pb = yaml.safe_load(f.read_text(encoding="utf-8"))
                if pb and pb.get("triggers") and pb.get("steps"):
                    playbooks.append(pb)
            except Exception as e:
                logging.warning(f"Playbook {f.name} không hợp lệ, bỏ qua: {e}")
    except Exception as e:
        logging.warning(f"Không load được playbooks: {e}")
    _playbook_cache = playbooks
    return playbooks


def _match_playbook(question: str, graph_context: str) -> dict | None:
    """Chọn playbook: trigger khớp câu hỏi + scope có đủ bảng + không quá cụ thể."""
    q = question.lower()
    ctx = (graph_context or "").lower()
    for pb in _load_playbooks():
        if not any(t.lower() in q for t in pb.get("triggers", [])):
            continue
        if any(s.lower() in q for s in pb.get("skip_if_contains", [])):
            continue
        if not all(tb.lower() in ctx for tb in pb.get("requires_tables", [])):
            continue
        return pb
    return None


async def run_playbook(state: AgentState) -> dict:
    """Chạy chuỗi bước phân tích của playbook, tổng hợp insight theo insight_guide."""
    pb = state["playbook"]
    original_q = state["queries_history"][-1]
    # (Event "📘 Kích hoạt..." đã phát từ classify_intent để user thấy ngay)
    events: list[dict] = []
    main_results, main_sql = None, None

    # Follow-up thường thiếu kỳ; câu hỏi có thể kèm PHẠM VI (vùng/tỉnh/kênh/NPP/nhóm SP).
    # Truyền hội thoại gần đây + bắt buộc mọi bước dùng CÙNG kỳ VÀ CÙNG phạm vi lọc —
    # nếu không, các bước lệch nhau (vd tổng đã lọc Đà Nẵng nhưng nhân viên chạy toàn quốc).
    recent = "\n".join(f"- {q}" for q in state["queries_history"][-3:])
    period_ctx = (
        f"(Hội thoại gần đây của người dùng, câu cuối là câu đang hỏi:\n{recent}\n"
        f"QUY TẮC BẮT BUỘC cho truy vấn của bước này:\n"
        f"1. KỲ PHÂN TÍCH: suy ra từ hội thoại; không nêu rõ thì dùng tháng hiện tại.\n"
        f"2. PHẠM VI LỌC: nếu hội thoại giới hạn phạm vi (tỉnh/thành như Đà Nẵng, vùng, "
        f"kênh, NPP, nhóm sản phẩm...), truy vấn PHẢI áp đúng bộ lọc đó (JOIN bảng "
        f"customer/area/staff tương ứng nếu cần).\n"
        f"TẤT CẢ các bước của phân tích này phải dùng CÙNG kỳ và CÙNG phạm vi lọc.)")

    async def _run_step(step: dict) -> dict:
        """1 bước = sinh SQL (retry 1 lần) + execute. Các bước độc lập → chạy SONG SONG."""
        sub_q = f"{step['question']}\n{period_ctx}"
        sub_state = {**state, "queries_history": state["queries_history"][:-1] + [sub_q],
                     "validation_error": None}
        rows, sql, err = None, None, None
        for _attempt in range(2):  # 1 lần sinh + 1 lần tự sửa lỗi
            try:
                state_after_sql = await asyncio.to_thread(generate_sql, sub_state)
                sql = state_after_sql["sql_query"]
                
                # Accrue token usage from the sub_state (from generate_sql)
                if "total_prompt_tokens" in state_after_sql:
                    sub_state["total_prompt_tokens"] = state_after_sql["total_prompt_tokens"]
                    sub_state["total_completion_tokens"] = state_after_sql["total_completion_tokens"]
                    sub_state["api_calls_count"] = state_after_sql["api_calls_count"]

                sqlglot.parse_one(sql, read={"postgres": "postgres", "mysql": "mysql",
                                            "sqlite": "sqlite"}.get(state["db_type"], "postgres"))
                rows = await asyncio.to_thread(
                    state["loader_class"].execute_sql_query, sql, state["db_url"])
                err = None
                break
            except Exception as e:
                err = str(e)
                sub_state = {**sub_state, "validation_error": err}
        return {"title": step.get("title", step["id"]), "sql": sql,
                "rows": rows if rows is not None else [], "error": err,
                "usage": {
                    "prompt_tokens": sub_state.get("total_prompt_tokens", 0) - state.get("total_prompt_tokens", 0),
                    "completion_tokens": sub_state.get("total_completion_tokens", 0) - state.get("total_completion_tokens", 0),
                    "api_calls_count": sub_state.get("api_calls_count", 0) - state.get("api_calls_count", 0)
                }}

    
    total_pb_prompt = 0
    total_pb_completion = 0
    total_pb_calls = 0

    step_results = await asyncio.gather(*[_run_step(s) for s in pb["steps"]])
    for i, r in enumerate(step_results, 1):
        total_pb_prompt += r.get("usage", {}).get("prompt_tokens", 0)
        total_pb_completion += r.get("usage", {}).get("completion_tokens", 0)
        total_pb_calls += r.get("usage", {}).get("api_calls_count", 0)
        
        events.append({"type": "reasoning_step", "final_response": False,
                       "message": f"  {i}/{len(pb['steps'])} {r['title']}: "
                                  + (f"⚠️ {r['error'][:80]}" if r["error"] else f"{len(r['rows'])} dòng")})
        # Bước lỗi hoặc 0 dòng: đính kèm SQL vào trace để admin xác định root cause
        if (r["error"] or not r["rows"]) and r["sql"]:
            events.append({"type": "reasoning_step", "final_response": False,
                           "message": f"    ↳ SQL bước {i}: {' '.join(r['sql'].split())[:350]}"})
        if main_results is None and r["rows"]:
            main_results, main_sql = r["rows"], r["sql"]

    # Tổng hợp insight theo guide của sale leader
    digest = json.dumps(
        [{"buoc": r["title"], "loi": r["error"], "du_lieu": r["rows"][:15]} for r in step_results],
        ensure_ascii=False, default=str)[:12000]
    try:
        insight, pb_usage = run_completion(
            messages=[
                {"role": "system",
                 "content": "Bạn là sales leader phân tích số liệu cho team. "
                            "Tổng hợp các kết quả phân tích bên dưới theo đúng guide sau:\n\n"
                            + pb.get("insight_guide", "Tóm tắt các phát hiện chính, tiếng Việt.")
                            + "\n\nKIỂM TRA NHẤT QUÁN (bắt buộc, làm TRƯỚC khi viết): nếu số liệu "
                              "giữa các bước lệch nhau bất thường về độ lớn, kỳ hoặc phạm vi lọc "
                              "(vd tổng đã lọc Đà Nẵng 510tr nhưng bước nhân viên chạy toàn quốc "
                              "9 tỷ), thì bước lệch đã truy vấn SAI KỲ/PHẠM VI — KHÔNG dùng số của "
                              "bước lệch để kết luận; ghi chú ngắn 'số liệu bước X cần kiểm tra lại' "
                              "và chỉ phân tích từ các bước nhất quán.\n"
                              "ĐỊNH DẠNG BẮT BUỘC: KHÔNG dùng heading ###; **in đậm** cho tiêu đề "
                              "mục; mỗi mục cách nhau 1 dòng trống. Khi liệt kê nhiều thực thể "
                              "(nhân viên, khu vực, sản phẩm...), MỖI thực thể là MỘT bullet '-' "
                              "riêng một dòng theo mẫu: '- Tên — số liệu (nhận xét ngắn nếu cần)'. "
                              "TUYỆT ĐỐI không gộp nhiều thực thể vào một câu văn dài."},
                {"role": "user",
                 "content": f"Hội thoại gần đây (câu cuối là câu đang hỏi):\n{recent}\n\n"
                            f"Kết quả các bước phân tích (JSON):\n{digest}"},
            ],
            custom_model=state["custom_model"],
            custom_api_key=state["custom_api_key"],
            temperature=0.2,
            return_usage=True
        )
        insight = insight.strip()
        total_pb_prompt += pb_usage.get("prompt_tokens", 0)
        total_pb_completion += pb_usage.get("completion_tokens", 0)
        total_pb_calls += 1
    except Exception as e:
        logging.error(f"Playbook synthesis error: {e}")
        insight = "Đã chạy xong các bước phân tích nhưng lỗi khi tổng hợp insight."

    if main_results:
        events.append({"type": "sql_query", "data": main_sql, "final_response": False})
        events.append({"type": "query_result", "data": main_results, "final_response": False})
        return {"query_results": main_results, "sql_query": main_sql or "",
                "insight": insight, "execution_error": None, "events_to_yield": events,
                "total_prompt_tokens": state.get("total_prompt_tokens", 0) + total_pb_prompt,
                "total_completion_tokens": state.get("total_completion_tokens", 0) + total_pb_completion,
                "api_calls_count": state.get("api_calls_count", 0) + total_pb_calls}
    # Mọi bước đều lỗi/rỗng: vẫn trả insight (đi đường direct_reply trong format)
    return {"query_results": [], "sql_query": main_sql or "", "insight": insight,
            "direct_reply": insight, "execution_error": None, "events_to_yield": events,
            "total_prompt_tokens": state.get("total_prompt_tokens", 0) + total_pb_prompt,
            "total_completion_tokens": state.get("total_completion_tokens", 0) + total_pb_completion,
            "api_calls_count": state.get("api_calls_count", 0) + total_pb_calls}


def classify_intent(state: AgentState) -> dict:
    """Phân loại câu hỏi TRƯỚC khi sinh SQL — chào hỏi & ngoài scope trả lời thẳng.

    Fallback an toàn: mọi lỗi phân loại đều rơi về data_query (đi tiếp pipeline cũ).
    """
    question = state["queries_history"][-1]
    context_preview = (state.get("graph_context") or "")[:3000]

    # Follow-up elliptical ("top 20", "còn tháng trước?", "chi tiết hơn") chỉ hiểu được
    # khi thấy hội thoại — classifier PHẢI nhận context, không chỉ câu cuối.
    prev_qs = state["queries_history"][:-1][-3:]
    prev_ans = (getattr(state.get("chat_data"), "result", None) or [])[-1:]
    convo_block = ""
    if prev_qs:
        convo_block = "\n### HỘI THOẠI TRƯỚC ĐÓ (câu cần phân loại là câu TIẾP THEO của mạch này):\n"
        convo_block += "\n".join(f"- User: {q}" for q in prev_qs)
        for a in prev_ans:
            convo_block += f"\n- Trả lời gần nhất: {str(a)[:300]}"

    system_prompt = f"""Bạn là bộ định tuyến của hệ thống StrongBI phân tích đa cơ sở dữ liệu.
Phân loại tin nhắn cuối của người dùng thành đúng 1 trong 3 intent:

- "data_query": câu hỏi CÓ THỂ trả lời bằng truy vấn trên dữ liệu trong SCHEMA CONTEXT bên dưới (doanh thu, đơn hàng, sản phẩm, nhân viên, KPI, khách hàng, vùng miền...).
- "greeting": chào hỏi, cảm ơn, small talk, hỏi "bạn làm được gì" — không cần dữ liệu.
  QUAN TRỌNG: câu ngắn/elliptical ("top 20", "còn tháng trước?", "chi tiết hơn", "theo quận")
  khi HỘI THOẠI TRƯỚC ĐÓ đang bàn về dữ liệu = follow-up của mạch đó → PHẢI là "data_query"
  (kế thừa chủ đề/kỳ/phạm vi), TUYỆT ĐỐI không phải greeting.
- "out_of_scope": câu hỏi về dữ liệu/chủ đề KHÔNG có trong SCHEMA CONTEXT (vd: tồn kho nếu không có bảng kho, thời tiết, tin tức, chính trị...).

Trả về DUY NHẤT một JSON object, không markdown:
{{"intent": "...", "reply": "..."}}

Quy tắc viết "reply" (chỉ cho greeting/out_of_scope, tiếng Việt, giọng trợ lý thân thiện chuyên nghiệp):
- greeting: chào lại ngắn gọn + gợi ý 2-3 câu hỏi cụ thể user có thể hỏi dựa trên SCHEMA CONTEXT.
- out_of_scope: nói rõ "hiện chưa đủ dữ liệu/thông tin trong phạm vi hệ thống để trả lời" + nêu ngắn gọn hệ thống ĐANG có dữ liệu gì (từ SCHEMA CONTEXT) để user hỏi lại đúng hướng. TUYỆT ĐỐI không bịa số liệu.
- data_query: để "reply" là chuỗi rỗng.

### SCHEMA CONTEXT (tóm tắt):
{context_preview}

### BUSINESS CONTEXT:
{state.get('business_context') or 'Not provided.'}

{convo_block}
{_scope_gate_text()}"""
    try:
        raw, usage = run_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            custom_model=state["custom_model"],
            custom_api_key=state["custom_api_key"],
            temperature=0.0,
            return_usage=True
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip())
        parsed = json.loads(raw)
        intent = parsed.get("intent", "data_query")
        reply = (parsed.get("reply") or "").strip()
        if intent not in ("data_query", "greeting", "out_of_scope"):
            intent = "data_query"
        if intent != "data_query" and not reply:
            reply = ("Xin chào! Tôi là trợ lý phân tích dữ liệu bán hàng. Bạn có thể hỏi về "
                     "doanh thu, đơn hàng, sản phẩm, KPI nhân viên..." if intent == "greeting"
                     else "Hiện tôi chưa đủ dữ liệu trong phạm vi hệ thống để trả lời câu hỏi này. "
                          "Bạn có thể hỏi về doanh thu, đơn hàng, sản phẩm, nhân viên, khách hàng, KPI.")
        events = []
        playbook = None
        if intent == "data_query":
            # Phase 2 (feature flag): thử match playbook trước khi đi flow SQL đơn
            if _playbook_enabled():
                playbook = _match_playbook(question, state.get("graph_context") or "")
            if playbook:
                # Báo NGAY khi node này flush — node run_playbook chạy 60-90s mới nhả event
                # (giới hạn LangGraph stream theo node), user cần biết hệ thống đang làm gì.
                events.append({"type": "reasoning_step", "final_response": False,
                               "message": f"📘 Kích hoạt playbook '{playbook['name']}' — "
                                          f"{len(playbook['steps'])} bước phân tích chuyên sâu, "
                                          f"có thể mất 1-2 phút. Vui lòng đợi..."})
            else:
                events.append({"type": "reasoning_step", "final_response": False,
                               "message": "Bước 2: Câu hỏi thuộc phạm vi dữ liệu — sinh SQL..."})
        return {"intent": intent, "direct_reply": reply or None,
                "playbook": playbook, "events_to_yield": events,
                "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
                "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
                "api_calls_count": state.get("api_calls_count", 0) + 1}
    except Exception as e:
        logging.warning(f"Intent classification failed, fallback to data_query: {e}")
        return {"intent": "data_query", "direct_reply": None, "playbook": None, "events_to_yield": []}


def route_intent(state: AgentState):
    if state.get("intent") in ("greeting", "out_of_scope"):
        return "format"
    if state.get("playbook"):
        return "run_playbook"
    return "generate_sql"


def generate_sql(state: AgentState) -> dict:
    question = state["queries_history"][-1]
    context = state["graph_context"]
    instructions = state.get("instructions", "")
    val_error = state.get("validation_error")
    
    system_prompt = f"""You are an elite SQL Developer and Data Engineer. Your task is to translate a user's natural language question into a syntactically correct and highly optimized SQL query based STRICTLY on the provided Semantic & Database Context.
Target Database Dialect: {state['db_type']}

### SEMANTIC & SCHEMA CONTEXT:
You will be provided with either a Semantic Layer (Metrics and Dimensions) or a Raw Database Schema.
- A "Metric" represents a quantitative measure with a predefined SQL formula (e.g., SUM(revenue)).
- A "Dimension" represents an attribute to group or filter by (e.g., created_at, country).

### BUSINESS CONTEXT:
{state.get('business_context') or 'Not provided.'}
You must ensure the generated query aligns with the Business Context where applicable (e.g., focusing on specific KPIs if requested).

### STRICT RULES:
1. **Semantic Compliance**: If the user asks for concepts defined in the Context, you MUST use the exact formula, table, or column provided. Do not guess or invent column names.
2. **Aggregation & Grouping**: When querying a Metric alongside a Dimension, ensure proper aggregation and include a `GROUP BY` clause for the Dimension.
3. **Table Joins**: If querying across multiple tables, infer the correct `JOIN` paths from the schema structure or foreign keys. Use appropriate table aliases (e.g., `orders o`).
4. **Dialect Specifics**: Ensure all functions (e.g., date handling, string manipulation, casting) are 100% compatible with {state['db_type']}.
5. **No Hallucinations**: Do NOT query tables or columns that do not exist in the Context. If a column is missing, rely on what is available.
6. **Performance**: Avoid `SELECT *`. Only select the columns necessary to answer the question. Apply `LIMIT` if the user asks for "top N" or "best".
7. **Output Format**: Return ONLY the raw executable SQL query. Do not wrap it in markdown code blocks like ```sql or ```. Do not provide any explanations. Do not use quotes around the entire string.
8. **Display Names + KEY COLUMNS**: When grouping by ANY entity (province/district/store/staff/SKU), you MUST also SELECT that entity's key column (id/code — e.g. customer_id, staff_id, a.province) alongside the display name, so follow-up turns can bind by key. Original rule:  When grouping by an entity or a dimension (e.g., Area, Customer, Staff), you MUST `JOIN` the corresponding table and select its descriptive name column (e.g., `area_name`, `customer_name`, `staff_name`) in the `SELECT` clause. NEVER select only the `ID` column, as IDs are not readable for end-users.
9. **Date Context**: Today is {datetime.now().strftime('%Y-%m-%d')}. When the user asks for relative dates (e.g. 'this month', 'today', 'August'), assume this current year/month unless otherwise specified.
10. **Entity Binding — PRIMARY KEY FIRST**: If RECENT CONVERSATION contains a [DATA ...] block and the current question references an entity from it — by name, by pronoun ("nó", "cửa hàng đó"), or by POSITION ("cửa hàng thứ 2", "con cuối danh sách") — INCLUDING place names (tỉnh/quận: nếu digest có province_id/district_id của địa danh được nhắc thì DÙNG MÃ ĐÓ, cấm ILIKE tên) — you MUST filter by its primary key (customer_id, staff_id, product_id, *_code...) taken from that block. Resolve positions against the row order in [DATA]. Name ILIKE is a LAST RESORT only when no id/code exists in context, and must then include the conversation's scope filter (province/area...).
"""

    if state.get("security_filters"):
        system_prompt += f"10. **SECURITY POLICY (CRITICAL)**: You MUST strictly append the following filters to your WHERE clause to comply with Row-Level Security: {state['security_filters']}. Failure to do so is a severe security violation.\n"

    domain_hints = _load_domain_hints()
    if domain_hints:
        system_prompt += f"\n### DOMAIN KNOWLEDGE (áp dụng bắt buộc khi liên quan):\n{domain_hints}\n"

    system_prompt += """
### RESPONSE FORMAT:
SELECT ...
FROM ...
WHERE ...
"""

    # Follow-up: câu hỏi trước + tóm tắt trả lời trước giúp resolve "theo quận thì sao?",
    # kế thừa kỳ/phạm vi lọc khi câu hiện tại không nói lại.
    prev_qs = state["queries_history"][:-1][-4:]
    prev_answers = (getattr(state.get("chat_data"), "result", None) or [])[-4:]
    convo_ctx = ""
    if prev_qs:
        convo_ctx = ("\n### RECENT CONVERSATION (câu hiện tại có thể là follow-up):\n"
                     "QUY TẮC FOLLOW-UP: (1) kế thừa kỳ và phạm vi lọc (tỉnh/vùng/kênh) từ hội "
                     "thoại nếu câu hiện tại không nói khác; (2) nếu câu hỏi nhắc một thực thể "
                     "(cửa hàng/nhân viên/SKU) ĐÃ xuất hiện trong trả lời trước, phải hiểu là "
                     "ĐÚNG thực thể đó — ƯU TIÊN lọc bằng customer_id/id/mã code lấy từ khối "
                     "[DATA lượt này] của trả lời trước (chính xác tuyệt đối), hoặc thêm filter "
                     "phạm vi đang bàn (vd cùng tỉnh) — KHÔNG tìm trùng tên toàn quốc.\n")
        convo_ctx += "\n".join(f"- Người dùng đã hỏi: {q}" for q in prev_qs)
        for a in prev_answers:
            convo_ctx += f"\n- Trả lời trước (tóm tắt + data): {str(a)[:900]}"

    # DETERMINISTIC ENTITY RESOLVER: so khớp tên trong câu hỏi với digest [DATA]
    # của các lượt trước bằng code (không phụ thuộc LLM tự giác) → tiêm khoá đã resolve.
    # Match 2 chiều + bỏ dấu (câu viết tắt "FUJIMART" vẫn khớp "DC FUJIMART"); câu
    # elliptical không nhắc tên ("phân bổ từng tháng như nào") kế thừa entity đã match
    # ở câu hỏi trước gần nhất.
    resolved_lines = []
    try:
        import unicodedata

        def _norm(s: str) -> str:
            s = unicodedata.normalize("NFD", s.lower())
            return "".join(c for c in s if not unicodedata.combining(c))

        prev_all = [str(a) for a in (getattr(state.get("chat_data"), "result", None) or [])[-4:]]

        # Gom pool entity: (tên hiển thị, cột khoá, giá trị khoá)
        pool, pool_seen = [], set()

        def _pool_from_row(row) -> None:
            if not isinstance(row, dict):
                return
            keys = [(k, v) for k, v in row.items()
                    if ("_id" in k.lower() or "_code" in k.lower() or k.lower() == "id")
                    and v is not None]
            if not keys:
                return
            kk, kv = keys[0]
            if isinstance(kv, float) and kv.is_integer():
                kv = int(kv)  # JSON trả 208374.0 → WHERE customer_id = 208374
            for k, v in row.items():
                if isinstance(v, str) and len(v) > 2 and "name" in k.lower():
                    tag = (v, kk)
                    if tag not in pool_seen:
                        pool_seen.add(tag)
                        pool.append((v, kk, kv))

        # Nguồn 1 — digest [DATA] FE echo lại (chỉ có khi user được cấp tab data)
        n_digest = 0
        for a in prev_all:
            idx = a.find("[DATA")
            if idx < 0:
                continue
            jstart = a.find("[", a.find("]:", idx))
            if jstart < 0:
                continue
            frag = a[jstart:jstart + 4000]
            try:
                rows = json.loads(frag)
            except Exception:
                # digest có thể bị cắt — thử vá ] cuối
                try:
                    rows = json.loads(frag[:frag.rfind("}") + 1] + "]")
                except Exception:
                    continue
            n_digest += 1
            for row in rows if isinstance(rows, list) else []:
                _pool_from_row(row)

        # Nguồn 2 — trace server-side (chat_threads lưu FULL table_data KHÔNG lọc
        # ui_permissions): user bị chặn tab data thì FE không bao giờ có digest để
        # echo (stream bị lọc từ server), nên tra ngược các lượt trước của chính
        # user này trên graph này theo câu hỏi mà FE gửi trong `chat`.
        n_db_rows = 0
        prev_qs_ctx = state["queries_history"][:-1][-4:]
        if prev_qs_ctx and state.get("user_id") and state.get("graph_id"):
            try:
                from api.auth.models import ChatThread
                from api.database import get_session_factory
                _db = get_session_factory()()
                try:
                    threads = (_db.query(ChatThread)
                               .filter(ChatThread.user_id == str(state["user_id"]),
                                       ChatThread.graph_id == str(state["graph_id"]),
                                       ChatThread.query.in_(prev_qs_ctx),
                                       ChatThread.status == "done")
                               .order_by(ChatThread.created_at.desc())
                               .limit(6).all())
                finally:
                    _db.close()
                for t in threads:
                    for row in (t.table_data or [])[:5]:
                        _pool_from_row(row)
                    n_db_rows += 1
            except Exception:
                logger.warning("Entity resolver: tra chat_threads lỗi (bỏ qua)", exc_info=True)

        def _match(q: str) -> dict:
            """Trả {tên: (cột khoá, giá trị)} các entity câu q nhắc tới.
            Ưu tiên tên nằm trọn trong câu; fallback: token dài (>=5, bỏ dấu) của câu
            nằm trong tên — token khớp NHIỀU tên khác nhau thì bỏ (nhập nhằng)."""
            q_norm = _norm(q)
            hits: dict = {}
            tok_owner: dict = {}
            for name, kk, kv in pool:
                n_norm = _norm(name)
                if n_norm and n_norm in q_norm:
                    hits.setdefault(name, (kk, kv))
                    continue
                n_tokens = set(re.split(r"[^0-9a-z]+", n_norm))
                for t in re.split(r"[^0-9a-z]+", q_norm):
                    if len(t) >= 5 and t in n_tokens:
                        tok_owner.setdefault(t, set()).add((name, kk, str(kv)))
            for t, owners in tok_owner.items():
                if len(owners) == 1:  # token chỉ trỏ đúng 1 entity → an toàn
                    name, kk, _ = next(iter(owners))
                    kv = next(kv for n, k, kv in pool if n == name and k == kk)
                    hits.setdefault(name, (kk, kv))
            return hits

        hits = _match(question)
        inherited = False
        if not hits:
            # Câu follow-up không nhắc tên → kế thừa entity của câu hỏi trước gần nhất
            for prev_q in reversed(state["queries_history"][:-1][-3:]):
                hits = _match(prev_q)
                if hits:
                    inherited = True
                    break
        for nval, (kk, kv) in hits.items():
            kv_sql = kv if isinstance(kv, (int, float)) else f"'{kv}'"
            note = " (kế thừa từ câu hỏi trước — câu hiện tại hỏi tiếp về entity này)" if inherited else ""
            resolved_lines.append(
                f"- \"{nval}\" → {kk} = {kv_sql} (BẮT BUỘC: WHERE {kk} = {kv_sql}, CẤM ILIKE tên này){note}")
        logger.info(
            "Entity resolver: prev_answers=%d digests=%d db_threads=%d pool=%d resolved=%d%s%s",
            len(prev_all), n_digest, n_db_rows, len(pool), len(resolved_lines),
            " (kế thừa)" if inherited else "",
            "" if (prev_all or prev_qs_ctx) else " — FE không gửi history (bundle cũ?)")
    except Exception:
        logger.warning("Entity resolver lỗi (bỏ qua, không chặn sinh SQL)", exc_info=True)
    if resolved_lines:
        convo_ctx += "\n### RESOLVED ENTITIES (hệ thống đã đối chiếu chính xác — PHẢI dùng):\n" \
                     + "\n".join(resolved_lines) + "\n"

    user_prompt = f"""### PROVIDED CONTEXT:
{context}
{convo_ctx}
### USER INSTRUCTIONS:
{instructions if instructions else 'None'}

### USER QUESTION:
{question}

Please generate the corresponding {state['db_type']} SQL query:"""
    
    if val_error:
        user_prompt += f"\n\n[PREVIOUS ATTEMPT FAILED WITH ERROR]: {val_error}\nPlease fix the SQL syntax and try again."
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    sql, usage = run_completion(
        messages=messages,
        custom_model=state["custom_model"],
        custom_api_key=state["custom_api_key"],
        temperature=0.0,
        return_usage=True
    )
    sql = sql.strip()
    
    # Cleanup formatting if LLM still returned markdown
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    
    sql = sql.strip()
    
    return {
        "sql_query": sql,
        "events_to_yield": [{
            "type": "sql_query",
            "data": sql,
            "final_response": False,
        }],
        "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
        "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
        "api_calls_count": state.get("api_calls_count", 0) + 1
    }

def validate_sql(state: AgentState) -> dict:
    sql = state["sql_query"]
    events = []
    is_destructive = False
    error_msg = None
    
    # 1. Check destructive
    _, is_destructive = detect_destructive_operation(sql)
    if is_destructive and is_general_graph(state["graph_id"]):
        error_msg = "Destructive operation (INSERT/UPDATE/DELETE) not allowed on demo graphs."
    
    # 2. Syntax validation with sqlglot
    if not error_msg:
        try:
            # Map db_type to sqlglot dialects roughly
            dialect_map = {"postgres": "postgres", "mysql": "mysql", "sqlite": "sqlite", "snowflake": "snowflake"}
            dialect = dialect_map.get(state["db_type"], "postgres")
            sqlglot.parse_one(sql, read=dialect)
        except sqlglot.errors.ParseError as e:
            error_msg = f"Syntax Error: {str(e)}"
            
    if error_msg:
        events.append({"type": "reasoning_step", "final_response": False, "message": f"Phát hiện lỗi cú pháp: {error_msg}. Đang tự động sửa..."})
        return {
            "validation_error": error_msg,
            "validation_attempts": state.get("validation_attempts", 0) + 1,
            "is_destructive": is_destructive,
            "events_to_yield": events
        }
        
    events.append({"type": "reasoning_step", "final_response": False, "message": "Bước 3: Thực thi truy vấn SQL hợp lệ..."})
    return {
        "validation_error": None,
        "validation_attempts": state.get("validation_attempts", 0) + 1,
        "is_destructive": is_destructive,
        "events_to_yield": events
    }

async def execute_sql(state: AgentState) -> dict:
    events = []
    try:
        sql = state["sql_query"]
        try:
            dialect_map = {"postgres": "postgres", "mysql": "mysql", "sqlite": "sqlite", "snowflake": "snowflake"}
            dialect = dialect_map.get(state["db_type"], "postgres")
            parsed = sqlglot.parse_one(sql, read=dialect)
            if isinstance(parsed, sqlglot.exp.Select) and not parsed.args.get("limit"):
                parsed = parsed.limit(500)
                sql = parsed.sql(dialect=dialect)
                logger.info("Auto-appended LIMIT 500 to query")
        except Exception as e:
            logger.warning(f"Could not auto-append LIMIT: {e}")

        # Run DB query in a separate thread to not block the async event loop
        query_results = await asyncio.to_thread(
            state["loader_class"].execute_sql_query, sql, state["db_url"]
        )
        
        events.append({"type": "query_result", "data": query_results, "final_response": False})
        return {"query_results": query_results, "execution_error": None, "events_to_yield": events, "sql_query": sql}
    except Exception as e:
        events.append({"type": "reasoning_step", "final_response": False, "message": f"Lỗi thực thi DB: {str(e)}"})
        return {"execution_error": str(e), "events_to_yield": events}

def generate_insight_and_chart(state: AgentState) -> dict:
    events = [{"type": "reasoning_step", "final_response": False, "message": "Bước 4: Sinh Insight và Biểu đồ (Charting)..."}]
    
    if not state.get("query_results"):
        return {"events_to_yield": events}
        
    try:
        agent = InsightAndChartAgent(custom_api_key=state["custom_api_key"], custom_model=state["custom_model"], custom_api_base=state["custom_api_base"])
        res = agent.generate(
            user_query=state["queries_history"][-1],
            sql_query=state["sql_query"],
            query_results=state["query_results"],
            schema_context=state["graph_context"],
            business_context=state.get("business_context")
        )
        
        insight = res.get("insight") if res else None
        chart_config = res if res and res.get("should_visualize") else None
        
        if chart_config:
            events.append({"type": "chart_config", "data": chart_config.get("option"), "chart_type": chart_config.get("chart_type"), "final_response": False})
            
        usage = res.get("usage", {}) if res else {}
            
        return {
            "insight": insight,
            "chart_config": chart_config,
            "events_to_yield": events,
            "total_prompt_tokens": state.get("total_prompt_tokens", 0) + usage.get("prompt_tokens", 0),
            "total_completion_tokens": state.get("total_completion_tokens", 0) + usage.get("completion_tokens", 0),
            "api_calls_count": state.get("api_calls_count", 0) + 1
        }
    except Exception as e:
        logging.error(f"Insight/Chart generation error: {e}")
        return {"events_to_yield": events}

def format_response(state: AgentState) -> dict:
    events = []

    if state.get("direct_reply"):
        # Greeting / out-of-scope: trả lời thẳng, không qua SQL
        ans = state["direct_reply"]
        events.append({"type": "ai_response", "final_response": True, "message": ans})
    elif state.get("execution_error"):
        ans = f"Lỗi khi chạy SQL: {state['execution_error']}"
        events.append({"type": "error", "final_response": True, "message": ans})
    elif state.get("validation_error") and state.get("validation_attempts", 0) >= 3:
        ans = f"Không thể sinh SQL hợp lệ sau nhiều lần thử. Lỗi cuối: {state['validation_error']}"
        events.append({"type": "error", "final_response": True, "message": ans})
    else:
        results = state.get("query_results", [])
        num_rows = len(results) if isinstance(results, list) else 0
        
        if num_rows == 0:
            ans = "Truy vấn thành công nhưng không tìm thấy dữ liệu."
        else:
            ans = state.get("insight") or f"Đã tìm thấy {num_rows} bản ghi. (V4 Hybrid Architecture)"
            
        events.append({"type": "ai_response", "final_response": True, "message": ans})
        
    # Yield metrics event
    total_prompt = state.get("total_prompt_tokens", 0)
    total_comp = state.get("total_completion_tokens", 0)
    api_calls = state.get("api_calls_count", 0)
    
    from api.pricing.pricing import calculate_cost
    model_name = state.get("custom_model")
    cost_usd = calculate_cost(model_name, total_prompt, total_comp) if model_name else 0.0
    
    events.append({
        "type": "metrics",
        "data": {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_comp,
            "total_tokens": total_prompt + total_comp,
            "cost_usd": cost_usd,
            "api_calls_count": api_calls
        },
        "final_response": False
    })
        
    return {"final_answer": ans, "events_to_yield": events}

def route_validation(state: AgentState):
    if state.get("validation_error"):
        if state.get("validation_attempts", 0) >= 3:
            return "format" # Give up after 3 retries
        return "generate_sql" # Feedback loop
    return "execute"

def route_execution(state: AgentState):
    if state.get("execution_error"):
        return "format"
    return "insight_chart"

# Build Graph V4
builder = StateGraph(AgentState)
builder.add_node("init", init_state)
builder.add_node("retrieve", retrieve_schema)
builder.add_node("classify_intent", classify_intent)
builder.add_node("run_playbook", run_playbook)
builder.add_node("generate_sql", generate_sql)
builder.add_node("validate_sql", validate_sql)
builder.add_node("execute", execute_sql)
builder.add_node("insight_chart", generate_insight_and_chart)
builder.add_node("format", format_response)

builder.add_edge(START, "init")
builder.add_edge("init", "retrieve")
builder.add_edge("retrieve", "classify_intent")
builder.add_conditional_edges("classify_intent", route_intent,
    {"generate_sql": "generate_sql", "run_playbook": "run_playbook", "format": "format"})
builder.add_edge("run_playbook", "format")
builder.add_edge("generate_sql", "validate_sql")
builder.add_conditional_edges("validate_sql", route_validation, {"generate_sql": "generate_sql", "format": "format", "execute": "execute"})
builder.add_conditional_edges("execute", route_execution, {"format": "format", "insight_chart": "insight_chart"})
builder.add_edge("insight_chart", "format")
builder.add_edge("format", END)

graph = builder.compile()

from api.core.ai_tracer import save_ai_trace

def _make_json_safe(d: dict) -> dict:
    safe_d = {}
    for k, v in d.items():
        if k in ["db", "loader_class"]:
            safe_d[k] = str(type(v))
        elif isinstance(v, (dict, list, str, int, float, bool, type(None))):
            safe_d[k] = v
        else:
            safe_d[k] = str(v)
    return safe_d

async def run_query_graph_v4(workspace_id: str, graph_id: str, chat_data: Any, db=None, user_id: str=None) -> AsyncGenerator[Union[dict, _Final], None]:
    initial_state = {
        "workspace_id": workspace_id,
        "user_id": user_id or workspace_id, # Fallback for old calls
        "graph_id": graph_id,
        "chat_data": chat_data,
        "db": db,
    }
    
    current_state = dict(initial_state)
    graph_trace = {
        "initial_state": _make_json_safe(initial_state),
        "steps": []
    }
    
    try:
        async for event in graph.astream(initial_state, stream_mode="updates"):
            for node_name, state_updates in event.items():
                if isinstance(state_updates, dict):
                    graph_trace["steps"].append({
                        "node": node_name,
                        "updates": _make_json_safe(state_updates)
                    })
                    current_state.update(state_updates)
                    if "events_to_yield" in state_updates:
                        for y_event in state_updates["events_to_yield"]:
                            yield y_event
    except Exception as e:
        graph_trace["steps"].append({
            "node": "CRITICAL_ERROR",
            "updates": {"error": str(e), "traceback": traceback.format_exc()}
        })
        raise
    finally:
        save_ai_trace("LangGraph_Execution_V4", {"user_id": user_id, "graph_id": graph_id}, graph_trace)
    
    final_state = current_state
    
    yield _Final(_build_query_result(
        sql_query=final_state.get("sql_query", ""),
        results=final_state.get("query_results", []),
        ai_response=final_state.get("final_answer", ""),
        confidence=1.0 if not final_state.get("execution_error") else 0.0,
        is_valid=final_state.get("validation_error") is None,
        is_destructive=final_state.get("is_destructive", False),
        execution_time=time.perf_counter() - final_state.get("start_time", time.perf_counter()),
        missing_information="",
        ambiguities="",
        explanation="",
        chart_config=final_state.get("chart_config"),
        error_message=final_state.get("execution_error") or final_state.get("validation_error"),
    ))
