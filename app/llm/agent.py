"""The hybrid tool-calling + RAG agent: system prompt, grounding guardrail,
and the main ask_trailbuddy() conversation loop."""
from datetime import datetime, timezone
import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from llm.client import get_llm
from llm.tools import TOOLS, TOOL_MAP
from services.chat_logger import log_chat_interaction


def get_llm_with_tools():
    """Lazy-load LLM with tools bound."""
    return get_llm().bind_tools(TOOLS)


_SYSTEM_CONTENT = (
    "You are TrailBuddy, a friendly and encouraging hiking companion.\n\n"
    "IMPORTANT: You have tools to access the user's personal hiking history, but you should ONLY use them "
    "when the user's question is specifically about THEIR past hikes or personal data.\n\n"
    "## When to USE tools:\n"
    "- Questions about specific hikes they've done (\"my hike to <area> or <location>\", \"hikes I did in May\")\n"
    "- Statistics about their hiking history (\"how many hikes\", \"total distance\", \"hardest hike\")\n"
    "- Personal notes or experiences (\"which hikes did I mention rain\", \"where did I feel tired\")\n"
    "- Comparisons within their data (\"my longest vs shortest hike\")\n\n"
    "## When to NOT use tools (answer directly):\n"
    "- General hiking advice (\"what should I bring on a hike\", \"how to prepare for hiking\")\n"
    "- Hypothetical questions (\"what would be a good beginner hike\", \"is 10km too much\")\n"
    "- Hiking tips and best practices (\"how to prevent blisters\", \"best time to hike\")\n"
    "- Questions about trails they haven't done yet\n"
    "- General conversation (\"hello\", \"what can you do\", \"tell me about hiking\")\n\n"
    "## Available Tools:\n"
    "- query_hikes_db(sql: str): Run a SQL SELECT query for ANY statistics. Use this for counts, "
    "sums, averages, or filtering. MUST use correctly formatted SQL.\n"
    "- search_hike_notes(query: str): Semantic search for 'feelings' or descriptions in notes.\n\n"
    "CRITICAL: If you need information from the user's hiking history, you MUST call one of the tools above. "
    "Do not just explain how to do it; actually trigger the tool call.\n\n"
    "Hikes have difficulty_score (1-50) and difficulty_level (Easy, Moderate, Challenging, Hard, Expert).\n"
    "When you use tools, provide specific numbers and dates. If no tools are needed, give friendly advice directly."
)


def _build_system_prompt() -> SystemMessage:
    """Build the system prompt with the real current date injected.

    This must be computed per-call (not cached at import time) so the
    assistant never falls back to its training-cutoff year (e.g. 2024)
    when reasoning about relative dates like "this year" or "this month".
    """
    today = datetime.now(timezone.utc).date()
    date_notice = (
        f"\n## Current Date\n"
        f"Today's real date is {today.isoformat()} (year {today.year}). "
        f"Always use this as the actual current date/year — never assume a different year, "
        f"including any year you may remember from your own training data. "
        f"When filtering by relative dates in SQL (e.g. 'this year', 'this month', 'last 7 days'), "
        f"prefer SQLite's date('now')/strftime('%Y'/'%m', 'now') functions so the database resolves "
        f"the date at query time, rather than hardcoding a year yourself.\n"
    )
    return SystemMessage(content=_SYSTEM_CONTENT + date_notice)


_NUMBER_TOKEN_RE = re.compile(r"-?\d[\d,]*\.?\d*")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

_GROUNDING_REMINDER = (
    "SYSTEM NOTICE: Your previous answer included hike details (dates, distances, "
    "elevations, durations, etc.) that do not match the raw tool results above. "
    "Do not invent, approximate, or reuse example numbers. Re-answer using ONLY "
    "the exact values returned by the tools. If the tools did not return enough "
    "information to answer, say so explicitly instead of making something up."
)

_UNGROUNDED_FALLBACK_MESSAGE = (
    "I wasn't able to confidently verify those hike details against your actual "
    "data, so I don't want to risk giving you incorrect numbers. Could you "
    "rephrase the question, or ask me to look up a specific hike or date range?"
)


def _collect_tool_output_text(messages: list) -> str:
    """Concatenate the raw content of all ToolMessages seen so far this turn."""
    return "\n".join(str(m.content) for m in messages if isinstance(m, ToolMessage))


def _extract_factual_numbers(text: str) -> list[float]:
    """Extract numbers that plausibly represent measured facts (distances,
    elevations, durations, difficulty scores) rather than list indices, small
    counts, or scale bounds like "1-50".
    """
    numbers = []
    for tok in _NUMBER_TOKEN_RE.findall(text):
        cleaned = tok.replace(",", "")
        if cleaned in ("", "-", "."):
            continue
        is_decimal = "." in cleaned
        digits_only = cleaned.lstrip("-").replace(".", "")
        if not is_decimal and len(digits_only) < 3:
            continue  # skip small integers like list numbers, counts, scale bounds
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue
    return numbers


def _is_answer_grounded(answer: str, tool_text: str) -> bool:
    """Check whether numeric/date facts claimed in the answer are backed by
    the raw tool output collected during this turn, so the model can't present
    fabricated hike data as if it came from the tools.
    """
    if not tool_text.strip():
        return True

    answer_dates = set(_DATE_RE.findall(answer))
    tool_dates = set(_DATE_RE.findall(tool_text))
    if any(d not in tool_dates for d in answer_dates):
        return False

    tool_numbers = _extract_factual_numbers(tool_text)
    for num in _extract_factual_numbers(answer):
        if not any(abs(num - t) < 0.05 for t in tool_numbers):
            return False

    return True


def _recover_missed_tool_call(response):
    """Small models sometimes emit a tool call as plain text instead of using
    the structured tool-calling API. Detect that and synthesize a tool_call.
    """
    if response.tool_calls:
        return

    if "query_hikes_db" in response.content:
        sql_match = re.search(r"(SELECT\b[^;]+)(?:;|$)", response.content, re.IGNORECASE)
        if sql_match:
            sql = sql_match.group(1).strip("`").strip()
            response.tool_calls = [{"name": "query_hikes_db", "args": {"sql": sql}, "id": "manual_sql"}]

    elif "search_hike_notes" in response.content:
        search_match = re.search(r"search_hike_notes\(['\"](.+?)['\"]\)", response.content)
        if search_match:
            query = search_match.group(1)
            response.tool_calls = [{"name": "search_hike_notes", "args": {"query": query}, "id": "manual_search"}]


def _execute_tool_calls(response, messages: list, sources: list[str]) -> None:
    """Invoke each requested tool, append results to messages, and record a
    deterministic execution trace of the call for the UI.

    Small/local models sometimes emit multiple tool_calls with identical
    (name, args) but different ids in the same response (duplicate parallel
    tool calls). Every id still needs a matching ToolMessage, but we only
    actually invoke the tool once per unique (name, args) pair and reuse the
    cached result for the rest, so duplicate calls don't run the same SQL
    query / search twice or show duplicate "Tools used" entries.
    """
    results_by_call: dict[str, str] = {}

    for tc in response.tool_calls:
        args_obj = tc.get("args", {})
        if not isinstance(args_obj, dict):
            args_obj = {"value": args_obj}
        args_json = json.dumps(args_obj, ensure_ascii=True, sort_keys=True)
        cache_key = f"{tc['name']}:{args_json}"

        is_duplicate = cache_key in results_by_call
        if is_duplicate:
            result = results_by_call[cache_key]
        else:
            tool_fn = TOOL_MAP[tc["name"]]
            result = tool_fn.invoke(tc["args"])
            results_by_call[cache_key] = result

        tool_call_id = tc.get("id")
        if tool_call_id is not None:
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))
        else:
            messages.append(ToolMessage(content=str(result)))

        if is_duplicate:
            continue  # don't show the same call twice in "Tools used"

        pretty_args = json.dumps(args_obj, ensure_ascii=True, indent=2)
        trace = (
            f"Tool: {tc['name']}\n"
            f"Call ID: {tc.get('id', 'n/a')}\n"
            f"Args:\n```json\n{pretty_args}\n```"
        )
        sources.append(trace)


def _extract_token_usage(response) -> tuple[int, int]:
    """Extract input/output token counts from a LangChain message response.

    ChatOllama may expose token counts in ``usage_metadata`` or in
    ``response_metadata`` (``prompt_eval_count`` / ``eval_count``). Fall back
    to zeros when neither source is available.
    """
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if input_tokens is not None and output_tokens is not None:
            return int(input_tokens), int(output_tokens)

    metadata = getattr(response, "response_metadata", {}) or {}
    input_tokens = metadata.get("prompt_eval_count")
    output_tokens = metadata.get("eval_count")
    if input_tokens is not None and output_tokens is not None:
        return int(input_tokens), int(output_tokens)

    return 0, 0


def _process_agent_iteration(
    response,
    messages: list,
    sources: list[str],
    used_tools: bool,
    grounding_retries: int,
    tool_names: list[str],
) -> tuple[bool, int, bool]:
    """Handle one LLM response: execute tools or validate grounding.

    Returns a tuple of (should_continue, grounding_retries_remaining,
    used_tools_after_this_iteration).
    """
    if response.tool_calls:
        for tc in response.tool_calls:
            name = tc.get("name")
            if name and name not in tool_names:
                tool_names.append(name)
        _execute_tool_calls(response, messages, sources)
        return True, grounding_retries, True

    is_grounded = _is_answer_grounded(
        response.content, _collect_tool_output_text(messages)
    )
    if used_tools and not is_grounded:
        if grounding_retries > 0:
            grounding_retries -= 1
            messages.append(HumanMessage(content=_GROUNDING_REMINDER))
            return True, grounding_retries, used_tools
        response.content = _UNGROUNDED_FALLBACK_MESSAGE
    return False, grounding_retries, used_tools


def _log_chat_interaction_safe(
    *,
    question: str,
    input_tokens: int,
    output_tokens: int,
    tools_called: bool,
    tool_names: list[str],
    latency_ms: int,
) -> None:
    """Persist chat metrics; failures are swallowed so chat never breaks."""
    try:
        log_chat_interaction(
            question=question,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tools_called=tools_called,
            tool_names=tool_names,
            latency_ms=latency_ms,
            model=get_llm().model,
        )
    except Exception:
        # Logging is best-effort; never let telemetry issues break the UI.
        pass


def ask_trailbuddy(question: str) -> tuple[str, list[str]]:
    """Run the hybrid tool-calling + RAG agent and return (answer, sources)."""
    start_time = time.perf_counter()
    messages = [_build_system_prompt(), HumanMessage(content=question)]
    sources: list[str] = []
    llm_with_tools = get_llm_with_tools()
    used_tools = False
    grounding_retries = 2
    total_input_tokens = 0
    total_output_tokens = 0
    tool_names: list[str] = []

    for _ in range(10):  # safety cap on iterations
        response = llm_with_tools.invoke(messages)
        _recover_missed_tool_call(response)
        messages.append(response)

        input_tokens, output_tokens = _extract_token_usage(response)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

        should_continue, grounding_retries, used_tools = _process_agent_iteration(
            response, messages, sources, used_tools, grounding_retries, tool_names
        )
        if not should_continue:
            break

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    _log_chat_interaction_safe(
        question=question,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        tools_called=used_tools,
        tool_names=tool_names,
        latency_ms=latency_ms,
    )

    return response.content, sources
