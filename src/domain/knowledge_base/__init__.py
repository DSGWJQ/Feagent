"""Knowledge base package for RAG functionality"""

from .entities.document import Document
from .entities.document_chunk import DocumentChunk
from .entities.knowledge_base import KnowledgeBase

__all__ = ["Document", "DocumentChunk", "KnowledgeBase"]
