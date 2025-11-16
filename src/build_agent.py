# build_agent.py
"""
Build and compile the email automation agent with all integrations.
"""

import os
from dotenv import load_dotenv
from typing import Optional

from src.utils import make_llm, build_workflow, get_checkpointer
from src.vector_db import get_vector_store
from src.tools import get_web_search_tool

# Load environment variables
load_dotenv()

def build_email_agent(
    db_path: str = "email_agent.db",
    vector_db_path: str = "./chroma_db",
    vector_data_dir: str = "vector_data",
    model: str = "gpt-4o-mini",
    enable_langfuse: bool = True
):
    """
    Build and compile the complete email automation agent.
    
    Args:
        db_path: Path to SQLite database for persistence
        vector_db_path: Path to ChromaDB persistence directory
        vector_data_dir: Directory containing markdown files for vector DB
        model: OpenAI model to use
        enable_langfuse: Whether to enable Langfuse monitoring
    
    Returns:
        Compiled LangGraph agent
    """
    print("🔧 Building email automation agent...")
    
    # Initialize LLM
    llm = make_llm(model=model)
    print(f"✅ LLM initialized: {model}")
    
    # Initialize vector store
    try:
        vector_store = get_vector_store(
            persist_directory=vector_db_path,
            data_dir=vector_data_dir
        )
        print("✅ Vector store initialized")
    except Exception as e:
        print(f"⚠️  Vector store error: {e}")
        vector_store = None
    
    # Initialize web search tool
    search_tool = get_web_search_tool()
    if search_tool:
        print("✅ Web search tool initialized")
    else:
        print("⚠️  Web search tool not available")
    
    # Build workflow
    workflow = build_workflow(
        llm=llm,
        vector_store=vector_store,
        search_tool=search_tool
    )
    print("✅ Workflow built")
    
    # Setup Langfuse if enabled (will be used via callbacks in email_agent_chat.py)
    langfuse_handler = None
    if enable_langfuse:
        try:
            langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            
            if langfuse_public_key and langfuse_secret_key:
                from langfuse.langchain import CallbackHandler
                langfuse_handler = CallbackHandler()
                print("✅ Langfuse callback handler configured")
            else:
                print("⚠️  Langfuse keys not found. Monitoring disabled.")
        except Exception as e:
            print(f"⚠️  Langfuse setup error: {e}")
            langfuse_handler = None
    
    # Return workflow and components (checkpointer will be handled in main)
    print("✅ Workflow ready for compilation")
    
    return workflow, llm, vector_store, search_tool, langfuse_handler

if __name__ == "__main__":
    # Test build
    workflow, llm, vector_store, search_tool, langfuse_handler = build_email_agent()
    from utils import get_checkpointer
    with get_checkpointer("email_agent.db") as checkpointer:
        agent = workflow.compile(
            checkpointer=checkpointer,
            interrupt_after=["reviewer"]  # Show review status before human approval
        )
        print("\n🎉 Agent built successfully!")
        print("Use email_agent_chat.py to interact with the agent.")

