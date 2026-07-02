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


def _extract_json_from_llm_response(content: str, expected_schema: dict = None) -> dict | None:
    """Robustly extract and validate JSON from LLM response.
    
    Args:
        content: Raw LLM response text
        expected_schema: Optional dict mapping field names to (type, default_value) tuples
        
    Returns:
        Parsed and validated JSON dict, or None if extraction fails
    """
    if not content:
        return None
    
    content = content.strip()
    
    # Strategy 1: Try to extract JSON from markdown code blocks
    json_patterns = [
        r'```json\s*\n(.+?)\n```',  # ```json ... ```
        r'```\s*\n(.+?)\n```',       # ``` ... ```
        r'`([{\[].*?[}\]])`',         # `{...}` or `[...]`
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match.strip())
                if isinstance(result, dict):
                    return _validate_json_schema(result, expected_schema)
            except json.JSONDecodeError:
                continue
    
    # Strategy 2: Find first valid JSON object or array in the text
    # Look for { ... } or [ ... ] patterns
    json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_obj_pattern, content)
    
    for match in matches:
        try:
            result = json.loads(match)
            if isinstance(result, dict):
                return _validate_json_schema(result, expected_schema)
        except json.JSONDecodeError:
            continue
    
    # Strategy 3: Try parsing the entire content as JSON
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return _validate_json_schema(result, expected_schema)
    except json.JSONDecodeError:
        pass
    
    return None


def _validate_json_schema(data: dict, expected_schema: dict = None) -> dict:
    """Validate and coerce JSON data to expected schema.
    
    Args:
        data: Parsed JSON dict
        expected_schema: Dict mapping field names to (type, default_value) tuples
        
    Returns:
        Validated dict with coerced types
    """
    if not expected_schema:
        return data
    
    validated = {}
    for field, (expected_type, default_value) in expected_schema.items():
        value = data.get(field, default_value)
        
        if value is None:
            validated[field] = default_value
            continue
        
        # Type coercion with error handling
        try:
            if expected_type == float:
                validated[field] = float(value)
            elif expected_type == int:
                validated[field] = int(value)
            elif expected_type == str:
                validated[field] = str(value)
            elif expected_type == bool:
                if isinstance(value, bool):
                    validated[field] = value
                elif isinstance(value, str):
                    validated[field] = value.strip().lower() in {"true", "1", "yes", "y", "on"}
                else:
                    validated[field] = bool(value)
                validated[field] = value
        except (ValueError, TypeError):
            validated[field] = default_value
    
    return validated


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
        existing = vectorstore.get(include=[])  # fetch ids only
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

# Comprehensive SQL injection protection
_ALLOWED_SQL = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

# Dangerous keywords that should never appear in user queries
_DANGEROUS_SQL_KEYWORDS = [
    'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
    'PRAGMA', 'ATTACH', 'DETACH', 'EXEC', 'EXECUTE',
    'REPLACE', 'TRUNCATE', 'GRANT', 'REVOKE'
]

_SQL_SCHEMA = (
    "Table: hikes\n"
    "Columns: id INTEGER, hike_date TEXT (YYYY-MM-DD), title TEXT, "
    "distance REAL (km), elevation_gain REAL (meters), "
    "duration_minutes INTEGER, notes TEXT, "
    "difficulty_score REAL, difficulty_level TEXT, created_at TEXT"
)


def _validate_sql_query(sql: str) -> tuple[bool, str]:
    """Validate SQL query for security. Returns (is_valid, error_message)."""
    # Remove comments to prevent hidden commands
    sql_no_comments = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql_no_comments = re.sub(r'/\*.*?\*/', '', sql_no_comments, flags=re.DOTALL)
    
    # Check for multiple statements (semicolon-separated)
    if ';' in sql_no_comments.rstrip(';'):
        return False, "Error: multiple statements not allowed"
    
    # Check it starts with SELECT
    if not _ALLOWED_SQL.match(sql_no_comments.strip()):
        return False, "Error: only SELECT queries are permitted"
    
    # Check for dangerous keywords
    sql_upper = sql_no_comments.upper()
    for keyword in _DANGEROUS_SQL_KEYWORDS:
        # Use word boundaries to avoid false positives in column names
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"Error: dangerous keyword '{keyword}' not allowed"
    
    # Ensure only querying the 'hikes' table or using it in joins
    # This prevents querying system tables like sqlite_master
    # Ensure only querying the 'hikes' table (or 'ranking') in any FROM/JOIN clause.
    # This prevents querying system tables like sqlite_master via JOINs or nested queries.
    table_refs = re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w]*)", sql_no_comments, flags=re.IGNORECASE)
    for table in table_refs:
        if table.lower() not in ["hikes", "ranking"]:
            return False, f"Error: access to table '{table}' not allowed"
    
    return True, ""


@tool
def query_hikes_db(sql: str) -> str:
    """Run a read-only SQL SELECT query against the hikes database.

    Schema - hikes(id, hike_date TEXT YYYY-MM-DD, title TEXT,
    distance REAL km, elevation_gain REAL meters,
    duration_minutes INTEGER, notes TEXT, created_at TEXT).

    Use this tool for exact numbers, counts, sums, averages, rankings,
    or filtering by date / distance / elevation.
    """
    # Multi-layer validation
    is_valid, error_msg = _validate_sql_query(sql)
    if not is_valid:
        return error_msg
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Enable read-only mode for extra safety
            conn.execute("PRAGMA query_only = ON")
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
    
    # Use robust JSON extraction
    result = _extract_json_from_llm_response(response.content, {
        "difficulty_score": (float, None),
        "difficulty_level": (str, None)
    })
    
    if result:
        return {
            "difficulty_score": result.get("difficulty_score", 0.0),
            "difficulty_level": result.get("difficulty_level", "Unknown")
        }
    
    # Fallback to local calculation if LLM fails
    print("Failed to extract valid JSON from LLM response for difficulty prediction")
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
    "IMPORTANT: You have tools to access the user's personal hiking history, but you should ONLY use them "
    "when the user's question is specifically about THEIR past hikes or personal data.\n\n"
    "## When to USE tools:\n"
    "- Questions about specific hikes they've done (\"my hike to Horgen\", \"hikes I did in May\")\n"
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
    "- query_hikes_db: SQL queries for statistics, counts, sums, filtering by date/distance/elevation\n"
    f"  {_SQL_SCHEMA}\n"
    "- search_hike_notes: Semantic search over their hike notes and descriptions\n\n"
    "Hikes have difficulty_score (1-50) and difficulty_level (Easy, Moderate, Challenging, Hard, Expert).\n"
    "When you do use tools, provide specific numbers and dates. Otherwise, give friendly, helpful advice directly."
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
