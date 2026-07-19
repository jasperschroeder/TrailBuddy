"""Chroma vectorstore management for semantic search over hike notes."""
from langchain_community.vectorstores import Chroma

import config
from db.hikes_repository import get_all_hikes
from llm.client import get_embeddings

# Module-level path (monkeypatch-friendly for evaluation fixtures), mirroring
# the pattern previously used by utils/rag.py's CHROMA_PATH global.
CHROMA_PATH = config.CHROMA_PATH
CHROMA_COLLECTION = config.CHROMA_COLLECTION


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
