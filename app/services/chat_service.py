"""Thin wrapper over the llm agent + vectorstore, exposed as one import for
the Chat page so it doesn't need to know about the llm package internals."""
from llm.agent import ask_trailbuddy
from llm.vectorstore import sync_vectorstore

__all__ = ["ask_trailbuddy", "sync_vectorstore"]
