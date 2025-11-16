# tools.py
"""
External tools for the email automation agent.
"""

import os
from typing import List, Dict, Any

try:
    # Try new langchain-tavily package first
    try:
        from langchain_tavily import TavilySearch
    except ImportError:
        # Fallback to deprecated version
        from langchain_community.tools.tavily_search import TavilySearchResults
        TavilySearch = None
    from langchain_core.tools import Tool
except Exception:
    raise ImportError("Missing dependencies. Try: pip install langchain-tavily or langchain-community tavily-python")

def create_web_search_tool(max_results: int = 3) -> Tool:
    """
    Create a web search tool using Tavily.
    
    Args:
        max_results: Maximum number of search results to return
    
    Returns:
        Tool instance for web search
    """
    try:
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            print("⚠️  TAVILY_API_KEY not found. Web search will be disabled.")
            return None
        
        # Use new langchain-tavily if available, otherwise fallback
        if TavilySearch is not None:
            # New API
            search = TavilySearch(api_key=tavily_api_key, max_results=max_results)
            # TavilySearch is already a tool, but we can wrap it for consistency
            web_search_tool = Tool(
                name="web_search",
                description=(
                    "Search the web for current information, company details, "
                    "recent news, or any external context needed for professional emails."
                ),
                func=lambda query: search.invoke({"query": query})
            )
        else:
            # Deprecated API (fallback)
            search = TavilySearchResults(max_results=max_results, api_key=tavily_api_key)
            web_search_tool = Tool(
                name="web_search",
                description=(
                    "Search the web for current information, company details, "
                    "recent news, or any external context needed for professional emails."
                ),
                func=lambda query: search.invoke({"query": query})
            )
        
        return web_search_tool
    except Exception as e:
        print(f"⚠️  Error creating web search tool: {e}")
        return None

def get_web_search_tool() -> Tool:
    """Get web search tool (convenience function)."""
    return create_web_search_tool()

