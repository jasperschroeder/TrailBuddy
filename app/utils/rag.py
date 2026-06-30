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
# Path relative to project root
ROOT_DIR = Path(__file__).parents[2]
DATA_DIR = ROOT_DIR / "data"
CHROMA_PATH = DATA_DIR / "chroma_db"
CHROMA_COLLECTION = "trailbuddy_hikes"

# Lazy initialization cache
_embeddings = None
_llm = None


def get_embeddings():
    """Lazy-load embeddings model on first use."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en-v1.5")
    return _embeddings


def get_llm():
    """Lazy-load LLM on first use."""
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            model="qwen2.5:7b",
            temperature=0.7,
            num_ctx=4096,
        )
    return _llm


# Vectorstore helpers (RAG over notes / free-text)

def _prepare_hike_doc(hike: dict) -> tuple[str, dict, str]:
    """Format a single hike for indexing."""
    text = (
        f"Hike ID: {hike.get('id')}\n"
        f"Title: {hike.get('title', 'Untitled')}\n"
        f"Date: {hike.get('hike_date')}\n"
        f"Distance: {hike.get('distance', 0)} km\n"
        f"Elevation Gain: {hike.get('elevation_gain', 0)} m\n"
        f"Duration: {hike.get('duration_minutes', 'unknown')} minutes\n"
        f"Difficulty Score: {hike.get('difficulty_score', 'N/A')}\n"
        f"Difficulty Level: {hike.get('difficulty_level', 'N/A')}\n"
        f"Notes: {hike.get('notes', 'No notes provided')}"
    )
    metadata = {
        "hike_id": hike.get('id'),
        "hike_date": hike.get('hike_date') or "unknown"
    }
    doc_id = str(hike.get('id'))
    return text, metadata, doc_id


def _open_vectorstore() -> Chroma:
    """Open the persisted hikes collection without rewriting it."""
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_PATH),
    )


def sync_vectorstore():
    """Only adds missing hikes to the vector store."""
    hikes = get_all_hikes()
    if not hikes:
        return "No hikes in the database to index."

    vectorstore = _open_vectorstore()
    
    # Get existing IDs from Chroma
    try:
        existing = vectorstore.get()
        indexed_ids = set(existing['ids'])
    except Exception:
        indexed_ids = set()

    to_index = [h for h in hikes if str(h['id']) not in indexed_ids]

    if not to_index:
        return "Vectorstore is already up to date."

    texts, metadatas, ids = [], [], []
    for hike in to_index:
        t, m, i = _prepare_hike_doc(hike)
        texts.append(t)
        metadatas.append(m)
        ids.append(i)

    # Incremental add
    vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    return f"Successfully indexed {len(to_index)} new hikes."


def get_or_create_vectorstore() -> Chroma:
    """Open existing collection, creating it on first use if needed."""
    try:
        vectorstore = _open_vectorstore()
        # Trigger sync in background or immediately if count is 0
        sync_vectorstore()
        return vectorstore
    except Exception:
        sync_vectorstore()
        return _open_vectorstore()


def rebuild_vectorstore():
    """Legacy rebuild function, now performs a sync."""
    return sync_vectorstore()


# Tool 1 - SQL for structured and aggregate queries

# Only allowing read-only SELECT queries for safety.
_ALLOWED_SQL = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

_SQL_SCHEMA = (
    "Table: hikes\n"
    "Columns: id INTEGER, hike_date TEXT (YYYY-MM-DD), title TEXT, "
    "distance REAL (km), elevation_gain REAL (meters), "
    "duration_minutes INTEGER, notes TEXT, "
    "difficulty_score REAL, difficulty_level TEXT, created_at TEXT"
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
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql.strip())
            rows = cursor.fetchall()
        if not rows:
            return "No results found."
        return json.dumps([dict(row) for row in rows], default=str)
    except sqlite3.Error as exc:
        return f"SQL error: {exc}"


def predict_hike_difficulty(distance: float, elevation_gain: float, notes: str = "") -> dict:
    """
    Predict hike difficulty using the LLM and RAG guidelines.
    """
    guidelines_path = Path(__file__).parent / "difficulty_guidelines.md"
    guidelines = ""
    if guidelines_path.exists():
        with open(guidelines_path, "r") as f:
            guidelines = f.read()

    prompt = f"""
    You are an expert hiking guide. Based on the following guidelines and hike details,
    predict a numerical difficulty score (1-50) and a level (Easy, Moderate, Challenging, Hard, Expert).

    GUIDELINES:
    {guidelines}

    HIKE DETAILS:
    - Distance: {distance} km
    - Elevation Gain: {elevation_gain} m
    - Notes: {notes}

    Return ONLY a JSON object with keys: "difficulty_score" (float) and "difficulty_level" (string).
    """

    response = get_llm().invoke([HumanMessage(content=prompt)])
    try:
        # Clean response if LLM adds markdown backticks
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        result = json.loads(content)
        return {
            "difficulty_score": float(result.get("difficulty_score", 0.0)),
            "difficulty_level": str(result.get("difficulty_level", "Unknown"))
        }
    except Exception as e:
        print(f"Error parsing LLM response for difficulty: {e}")
        # Fallback to local calculation if LLM fails
        from utils.difficulty import calculate_difficulty_score, get_difficulty_level
        score = calculate_difficulty_score(distance, elevation_gain)
        return {
            "difficulty_score": score,
            "difficulty_level": get_difficulty_level(score)
        }


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


def get_llm_with_tools():
    """Lazy-load LLM with tools bound."""
    return get_llm().bind_tools(_TOOLS)


_SYSTEM_CONTENT = (
    "You are TrailBuddy, a friendly and encouraging hiking companion.\n\n"
    "You have two tools:\n"
    "- query_hikes_db: use for numbers, counts, sums, rankings, date filters, and difficulty analysis.\n"
    f"  {_SQL_SCHEMA}\n"
    "- search_hike_notes: use for semantic/free-text search over hike notes and feelings.\n\n"
    "Hikes now have a difficulty_score and difficulty_level.\n"
    "Levels: Easy, Moderate, Challenging, Hard, Expert.\n"
    "Use one or both tools as needed, then give a clear, friendly answer with "
    "specific numbers, dates, and difficulty information when available. "
    "If you cannot find the information, say so honestly."
)
_SYSTEM_PROMPT = SystemMessage(content=_SYSTEM_CONTENT)


def ask_trailbuddy(question: str) -> tuple[str, list[str]]:
    """Run the hybrid tool-calling + RAG agent and return (answer, sources)."""
    messages = [_SYSTEM_PROMPT, HumanMessage(content=question)]
    sources: list[str] = []
    llm_with_tools = get_llm_with_tools()

    for _ in range(10):  # safety cap on iterations
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_fn = _TOOL_MAP[tc["name"]]
            result = tool_fn.invoke(tc["args"])
            tool_call_id = tc.get("id")
            if tool_call_id is not None:
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))
            else:
                messages.append(ToolMessage(content=str(result)))

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
