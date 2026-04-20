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
    model="qwen2.5:7b",
    temperature=0.5,
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


def ask_trailbuddy(question: str):
    """Ask a question and return answer + deduplicated sources."""
    vectorstore = get_or_create_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})

    docs = retriever.invoke(question)

    # Build clean context (one block per unique hike)
    context_parts = []
    seen_hike_ids = set()

    for doc in docs:
        content = doc.page_content.strip()
        # Extract hike ID to avoid duplicates
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

    # Deduplicated sources for display
    sources = []
    seen = set()
    for doc in docs:
        content = doc.page_content.strip()
        if "Hike ID:" in content:
            # Take a short unique snippet
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            snippet = "\n".join(lines[:4])  # max 4 lines
            if snippet not in seen:
                seen.add(snippet)
                sources.append(snippet)

    return answer, sources
