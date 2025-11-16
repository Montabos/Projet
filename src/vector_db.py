# vector_db.py
"""
Vector database setup and management for RAG.
"""

import os
from typing import List
from pathlib import Path

try:
    # Try new langchain-chroma package first (recommended)
    try:
        from langchain_chroma import Chroma
        USING_NEW_CHROMA = True
    except ImportError:
        # Fallback to deprecated version
        from langchain_community.vectorstores import Chroma
        USING_NEW_CHROMA = False
        import warnings
        # Suppress deprecation warnings for Chroma
        warnings.filterwarnings("ignore", message=".*Chroma.*deprecated.*", category=DeprecationWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community.vectorstores")
    
    from langchain_openai import OpenAIEmbeddings
    from langchain_core.documents import Document
    from langchain_community.document_loaders import TextLoader
except Exception:
    raise ImportError("Missing dependencies. Try: pip install langchain-chroma chromadb (or langchain-community)")

def load_markdown_files(data_dir: str = "data/vector_data") -> List[Document]:
    """Load all markdown files from the data directory."""
    documents = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        print(f"⚠️  Directory {data_dir} does not exist. Creating it.")
        data_path.mkdir(exist_ok=True)
        return documents
    
    for md_file in data_path.glob("*.md"):
        try:
            loader = TextLoader(str(md_file), encoding="utf-8")
            docs = loader.load()
            # Add metadata
            for doc in docs:
                doc.metadata["source"] = str(md_file.name)
                doc.metadata["file_type"] = "markdown"
            documents.extend(docs)
            print(f"✅ Loaded {md_file.name}")
        except Exception as e:
            print(f"⚠️  Error loading {md_file}: {e}")
    
    return documents

def create_vector_store(
    persist_directory: str = "artifacts/chroma_db",
    data_dir: str = "data/vector_data",
    embedding_model: str = "text-embedding-3-small"
) -> Chroma:
    """
    Create or load a Chroma vector store.
    
    Args:
        persist_directory: Directory to persist the vector store
        data_dir: Directory containing markdown files to index
        embedding_model: OpenAI embedding model to use
    
    Returns:
        Chroma vector store instance
    """
    embeddings = OpenAIEmbeddings(model=embedding_model)
    
    # Inform user which version is being used
    if not USING_NEW_CHROMA:
        print("ℹ️  Using langchain-community Chroma (consider installing langchain-chroma to remove deprecation warning)")
    
    # Check if vector store already exists
    if os.path.exists(persist_directory) and os.listdir(persist_directory):
        print(f"📂 Loading existing vector store from {persist_directory}")
        vector_store = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )
    else:
        print(f"🆕 Creating new vector store in {persist_directory}")
        # Load documents
        documents = load_markdown_files(data_dir)
        
        if not documents:
            print("⚠️  No documents found. Creating empty vector store.")
            # Create empty vector store
            vector_store = Chroma(
                persist_directory=persist_directory,
                embedding_function=embeddings
            )
        else:
            print(f"📄 Indexing {len(documents)} documents...")
            # Create vector store with documents
            vector_store = Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                persist_directory=persist_directory
            )
            print(f"✅ Vector store created with {len(documents)} documents")
    
    return vector_store

def get_vector_store(
    persist_directory: str = "./chroma_db",
    data_dir: str = "vector_data"
) -> Chroma:
    """
    Get or create vector store (convenience function).
    """
    return create_vector_store(persist_directory, data_dir)

