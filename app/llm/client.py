"""Lazy-loaded LLM and embeddings clients shared across the llm package."""
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings

import config

OLLAMA_MODEL = config.OLLAMA_MODEL

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
            model=OLLAMA_MODEL,
            base_url=config.OLLAMA_HOST,
            temperature=0.5,
            num_ctx=4096,
        )
    return _llm
