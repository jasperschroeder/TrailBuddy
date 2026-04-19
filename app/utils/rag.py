from langchain_ollama import OllamaLLM
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from utils.db import get_all_hikes
from pathlib import Path


# Configuration
DATA_DIR = Path("data")
CHROMA_PATH = DATA_DIR / "chroma_db"

# Initialize embeddings and LLM (local)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

llm = OllamaLLM(
    model="llama3.2:3b",
    temperature=0.7
)


def get_or_create_vectorstore():
    """Load existing vector store or create new one from hikes."""
    if CHROMA_PATH.exists():
        vectorstore = Chroma(
            persist_directory=str(CHROMA_PATH),
            embedding_function=embeddings
        )
    else:
        hikes = get_all_hikes()
        if not hikes:
            # Create empty vectorstore if no hikes yet
            vectorstore = Chroma.from_texts(
                texts=["No hikes logged yet."],
                embedding=embeddings,
                persist_directory=str(CHROMA_PATH)
            )
            return vectorstore

        # Prepare documents from hikes
        documents = []
        for hike in hikes:
            text = f"""
            Hike ID: {hike['id']}
            Title: {hike.get('title', 'Untitled')}
            Date: {hike.get('hike_date')}
            Distance: {hike.get('distance')} km
            Elevation Gain: {hike.get('elevation_gain')} m
            Duration: {hike.get('duration_minutes')} minutes
            Notes: {hike.get('notes', 'No notes')}
            """
            documents.append(text)

        vectorstore = Chroma.from_texts(
            texts=documents,
            embedding=embeddings,
            persist_directory=str(CHROMA_PATH)
        )
    return vectorstore


def get_rag_chain():
    """Build the RAG chain for answering questions."""
    vectorstore = get_or_create_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    template = """You are TrailBuddy, a friendly and helpful hiking companion.
    Use the following context from the user's personal hike history to answer the question.
    If you don't know the answer based on the context, say so honestly.
    Always be encouraging and practical.

    Context:
    {context}

    Question: {question}

    Answer:"""

    prompt = ChatPromptTemplate.from_template(template)

    chain = (
        {"context": retriever, "question": RunnablePassthrough()} |
        prompt |
        llm |
        StrOutputParser()
    )

    return chain


# For easier import
def ask_trailbuddy(question: str) -> str:
    """Simple function to ask a question and get an answer."""
    chain = get_rag_chain()
    return chain.invoke(question)
