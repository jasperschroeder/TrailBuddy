import re
import json
import sqlite3

from langchain_ollama import ChatOllama
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from utils.db import get_all_hikes, DB_PATH
from pathlib import Path


# Configuration
DATA_DIR = Path("data")
CHROMA_PATH = DATA_DIR / "chroma_db"
CHROMA_COLLECTION = "trailbuddy_hikes"

# Initialize embeddings and LLM (local)
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en-v1.5")  # Optionally replace with all-MiniLM-L6-v2

llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0.7,
    num_ctx=4096,
)


# Vectorstore helpers (RAG over notes / free-text)

def _build_documents(hikes: list[dict]) -> list[str]:
    docs = []
    for hike in hikes:
        text = (
            f"Hike ID: {hike.get('id')}\n"
            f"Title: {hike.get('title', 'Untitled')}\n"
            f"Date: {hike.get('hike_date')}\n"
            f"Distance: {hike.get('distance', 0)} km\n"
            f"Elevation Gain: {hike.get('elevation_gain', 0)} m\n"
            f"Duration: {hike.get('duration_minutes', 'unknown')} minutes\n"
            f"Notes: {hike.get('notes', 'No notes provided')}"
        )
        docs.append(text)
    return docs


def _open_vectorstore() -> Chroma:
    """Open the persisted hikes collection without rewriting it."""
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_PATH),
    )


def _build_or_rebuild_collection() -> Chroma:
    """Recreate the hikes collection content in-place (Windows lock-safe)."""
    hikes = get_all_hikes()
    documents = _build_documents(hikes) if hikes else ["No hikes logged yet."]

    # Delete collection entries instead of deleting DB files on disk.
    try:
        _open_vectorstore().delete_collection()
    except Exception:
        pass

    return Chroma.from_texts(
        texts=documents,
        embedding=embeddings,
        collection_name=CHROMA_COLLECTION,
        persist_directory=str(CHROMA_PATH),
    )


def get_or_create_vectorstore() -> Chroma:
    """Open existing collection, creating it on first use if needed."""
    try:
        vectorstore = _open_vectorstore()
        _ = vectorstore._collection.count()
        return vectorstore
    except Exception:
        return _build_or_rebuild_collection()


def rebuild_vectorstore():
    """Rebuild the hikes vector collection without deleting locked files."""
    return _build_or_rebuild_collection()


# Tool 1 - SQL for structured and aggregate queries

# Only allowing read-only SELECT queries for safety.
_ALLOWED_SQL = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

_SQL_SCHEMA = (
    "Table: hikes\n"
    "Columns: id INTEGER, hike_date TEXT (YYYY-MM-DD), title TEXT, "
    "distance REAL (km), elevation_gain REAL (meters), "
    "duration_minutes INTEGER, notes TEXT, created_at TEXT"
)


@tool
def query_hikes_db(sql: str) -> str:
    """Run a read-only SQL SELECT query against the hikes database.

    Schema - hikes(id, hike_date TEXT YYYY-MM-DD, title TEXT,
    distance REAL km, elevation_gain REAL meters,
    duration_minutes INTEGER, notes TEXT, created_at TEXT).

    Use this tool for exact numbers, counts, sums, averages, rankings,
    or filtering by date / distance / elevation.
    """
    if not _ALLOWED_SQL.match(sql.strip()):
        return "Error: only SELECT queries are permitted."
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql.strip())
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return "No results found."
        return json.dumps([dict(row) for row in rows], default=str)
    except sqlite3.Error as exc:
        return f"SQL error: {exc}"


# Tool 2 - RAG for semantic search over notes and descriptions

@tool
def search_hike_notes(query: str) -> str:
    """Search hike notes and descriptions using semantic similarity.

    Use this tool when the question is about the *feel*, *experience*, or
    free-text content of hikes — e.g. 'any hike where I mentioned rain?'
    or 'hikes where I felt tired'.
    """
    vectorstore = get_or_create_vectorstore()
    docs = vectorstore.as_retriever(search_kwargs={"k": 5}).invoke(query)
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


# Hybrid agent - Putting both together with a system prompt that explains when to use which tool.

_TOOLS = [query_hikes_db, search_hike_notes]
_TOOL_MAP = {t.name: t for t in _TOOLS}
_LLM_WITH_TOOLS = llm.bind_tools(_TOOLS)

_SYSTEM_CONTENT = (
    "You are TrailBuddy, a friendly and encouraging hiking companion.\n\n"
    "You have two tools:\n"
    "- query_hikes_db: use for numbers, counts, sums, rankings, date filters.\n"
    f"  {_SQL_SCHEMA}\n"
    "- search_hike_notes: use for semantic/free-text search over hike notes.\n\n"
    "Use one or both tools as needed, then give a clear, friendly answer with "
    "specific numbers and dates when available. "
    "If you cannot find the information, say so honestly."
)
_SYSTEM_PROMPT = SystemMessage(content=_SYSTEM_CONTENT)


def ask_trailbuddy(question: str) -> tuple[str, list[str]]:
    """Run the hybrid tool-calling + RAG agent and return (answer, sources)."""
    messages = [_SYSTEM_PROMPT, HumanMessage(content=question)]
    sources: list[str] = []

    for _ in range(10):  # safety cap on iterations
        response = _LLM_WITH_TOOLS.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_fn = _TOOL_MAP[tc["name"]]
            result = tool_fn.invoke(tc["args"])
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

            # Record a deterministic execution trace for the UI.
            args_obj = tc.get("args", {})
            if not isinstance(args_obj, dict):
                args_obj = {"value": args_obj}
            args_json = json.dumps(args_obj, ensure_ascii=True, indent=2)
            trace = (
                f"Tool: {tc['name']}\n"
                f"Call ID: {tc.get('id', 'n/a')}\n"
                f"Args:\n```json\n{args_json}\n```"
            )
            sources.append(trace)

    return response.content, sources
