import shutil

from langchain_ollama import OllamaLLM
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.db import get_all_hikes
from pathlib import Path


# Configuration
DATA_DIR = Path("data")
CHROMA_PATH = DATA_DIR / "chroma_db"

# Initialize embeddings and LLM (local)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

llm = OllamaLLM(
    # model="llama3.2:8b",
    model="qwen2.5:7b",
    temperature=0.3,
    num_ctx=8192
)


def get_or_create_vectorstore():
    hikes = get_all_hikes()

    if not hikes:
        vectorstore = Chroma.from_texts(
            texts=["No hikes logged yet."],
            embedding=embeddings,
            persist_directory=str(CHROMA_PATH)
        )
        return vectorstore

    documents = []
    for hike in hikes:
        text = f"""Hike ID: {hike.get('id')}
        Title: {hike.get('title', 'Untitled')}
        Date: {hike.get('hike_date')}
        Distance: {hike.get('distance', 0)} km
        Elevation Gain: {hike.get('elevation_gain', 0)} m
        Duration: {hike.get('duration_minutes', 'unknown')} minutes
        Notes: {hike.get('notes', 'No notes provided')}
        """
        documents.append(text)

    # Recreate fresh every time (safe for small number of hikes)
    vectorstore = Chroma.from_texts(
        texts=documents,
        embedding=embeddings,
        persist_directory=str(CHROMA_PATH)
    )
    return vectorstore


_ROUTE_PROMPT = ChatPromptTemplate.from_template(
    """
You are a routing assistant. Decide whether the following message requires looking up the user's personal hike
history/data to answer it properly. Reply with exactly one word: YES or NO.

Message: {question}"""
)


def _needs_rag(question: str) -> bool:
    """Ask the LLM whether the question requires hike data retrieval."""
    chain = _ROUTE_PROMPT | llm | StrOutputParser()
    result = chain.invoke({"question": question}).strip().upper()
    return result.startswith("YES")


def ask_trailbuddy(question: str):
    """Ask a question and return answer + sources only when RAG is actually needed."""
    import re

    if not _needs_rag(question):
        no_rag_prompt = ChatPromptTemplate.from_template(
            """You are TrailBuddy, a friendly hiking companion chatbot.
Answer the following message naturally. Do NOT reference any hike data or statistics.

Message: {question}

Response:"""
        )
        chain = no_rag_prompt | llm | StrOutputParser()
        return chain.invoke({"question": question}), []

    vectorstore = get_or_create_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})

    docs = retriever.invoke(question)

    # Build clean context (one block per unique hike)
    context_parts = []
    seen_hike_ids = set()

    for doc in docs:
        content = doc.page_content.strip()
        if "Hike ID:" in content:  # noqa
            try:
                hike_id_line = [line for line in content.split("\n") if "Hike ID:" in line][0]
                hike_id = hike_id_line.split(":")[1].strip()
                if hike_id in seen_hike_ids:
                    continue
                seen_hike_ids.add(hike_id)
            except Exception:  # noqa
                pass

        context_parts.append(content)

    context = "\n\n".join(context_parts)

    template = """You are TrailBuddy, a helpful and encouraging hiking companion.

Use ONLY the information in the Context below to answer the question.
Be specific and mention real numbers, dates, and notes when relevant.
If the context doesn't contain the answer, say "I don't have that information in your hike history yet."

Context:
{context}

Question: {question}

Answer in a natural, friendly tone:"""

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({"context": context, "question": question})

    # Only show sources if the answer contains specific hike data
    has_specific_data = bool(
        re.search(r'\d+\.?\d*\s*km', answer) or
        re.search(r'\d+\s*m\s*(?:elevation|gain)', answer) or
        re.search(r'\d{4}-\d{2}-\d{2}', answer) or
        re.search(r'\d+\s*minutes?\b', answer)
    )

    sources = []
    if has_specific_data and seen_hike_ids:
        seen = set()
        for doc in docs:
            content = doc.page_content.strip()
            if "Hike ID:" in content:
                try:
                    lines = [line.strip() for line in content.split("\n") if line.strip()]
                    snippet = "\n".join(lines[:4])
                    if snippet not in seen:
                        seen.add(snippet)
                        sources.append(snippet)
                except Exception:  # noqa
                    pass

    return answer, sources


def rebuild_vectorstore():
    """Delete the persisted ChromaDB and rebuild it from the current hike data."""
    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
    return get_or_create_vectorstore()
