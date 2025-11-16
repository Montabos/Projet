# utils.py
"""
Utility functions and definitions for the email automation agent.
"""

import os
from typing import List, TypedDict, Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.documents import Document
except Exception:
    raise ImportError("Missing dependency: langchain_openai. Try: pip install langchain-openai")

from langgraph.graph import StateGraph, END

# --- Agent State -------------------------------------------------------

class EmailAgentState(TypedDict, total=False):
    """State for the email automation agent."""
    # Input utilisateur
    user_input: str
    thread_id: Optional[str]
    
    # Classification
    intent: str  # REPLY_EMAIL | NEW_EMAIL | SUMMARIZE_THREAD
    intent_confidence: float
    
    # Retrieval
    retrieved_docs: List[Any]  # List[Document]
    context: str
    needs_web_search: bool
    
    # Web search
    web_results: List[Dict[str, Any]]
    enhanced_context: str
    
    # Drafting
    draft: str
    draft_metadata: Dict[str, Any]
    
    # Review
    review_approved: bool
    review_issues: List[str]
    review_suggestions: List[str]
    
    # Human interaction
    human_feedback: Optional[str]
    human_approved: bool
    final_email: Optional[str]
    
    # Tracking
    history: List[str]
    step_count: int

# --- LLM Setup ---------------------------------------------------------

def make_llm(model: str = "gpt-4o-mini", temperature: float = 0.7) -> "ChatOpenAI":
    """Initialize the language model."""
    return ChatOpenAI(model=model, temperature=temperature)

# --- Node Functions ----------------------------------------------------

def intent_classifier_node(state: EmailAgentState, llm: "ChatOpenAI") -> Dict[str, Any]:
    """Classify user intent and route to appropriate workflow."""
    user_input = state.get("user_input", "")
    
    prompt = (
        f"Analyze the following user request and classify it into one of these categories:\n"
        f"- REPLY_EMAIL: User wants to reply to an existing email or thread\n"
        f"- NEW_EMAIL: User wants to create a new email from scratch\n"
        f"- SUMMARIZE_THREAD: User wants to summarize an email conversation/thread\n\n"
        f"User request: {user_input}\n\n"
        f"Respond with only the category name (REPLY_EMAIL, NEW_EMAIL, or SUMMARIZE_THREAD)."
    )
    
    response = llm.invoke(prompt).content.strip()
    
    # Normalize response
    intent = "NEW_EMAIL"  # default
    if "REPLY" in response.upper():
        intent = "REPLY_EMAIL"
    elif "SUMMARIZE" in response.upper() or "SUMMARY" in response.upper():
        intent = "SUMMARIZE_THREAD"
    elif "NEW" in response.upper():
        intent = "NEW_EMAIL"
    
    confidence = 0.9 if intent in response.upper() else 0.7
    
    return {
        "intent": intent,
        "intent_confidence": confidence,
        "history": state.get("history", []) + [f"Classified intent: {intent}"]
    }

def retrieval_node(state: EmailAgentState, vector_store, llm: "ChatOpenAI" = None) -> Dict[str, Any]:
    """Retrieve relevant context from vector database."""
    intent = state.get("intent", "NEW_EMAIL")
    user_input = state.get("user_input", "")
    thread_id = state.get("thread_id")
    
    # Build search query based on intent
    if intent == "REPLY_EMAIL" or intent == "SUMMARIZE_THREAD":
        query = f"{user_input} email thread conversation"
    else:
        query = user_input
    
    # Perform vector search
    try:
        if vector_store:
            docs = vector_store.similarity_search(query, k=5)
            retrieved_content = "\n\n".join([doc.page_content for doc in docs])
        else:
            retrieved_content = "No vector store available."
            docs = []
    except Exception as e:
        print(f"⚠️  Vector search error: {e}")
        retrieved_content = ""
        docs = []
    
    # Let the LLM determine if web search is needed
    # This is more intelligent than keyword matching
    needs_web_search = False
    
    # Ask LLM if web search is needed
    web_search_prompt = (
        f"You are a decision agent. Analyze this email request and determine if a web search is needed.\n\n"
        f"User request: \"{user_input}\"\n"
        f"Available context from internal documents: {len(retrieved_content)} characters\n\n"
        f"IMPORTANT: Web search is ONLY needed if the email MUST mention:\n"
        f"- Recent news, current events, or breaking news\n"
        f"- Up-to-date information about specific companies/products that changes frequently\n"
        f"- Current market data, stock prices, or real-time statistics\n"
        f"- Information about external entities not in our internal documents\n"
        f"- Time-sensitive information that requires internet lookup\n\n"
        f"Web search is NOT needed for:\n"
        f"- Thank you emails, confirmations, scheduling, follow-ups\n"
        f"- Internal communications or standard business emails\n"
        f"- Emails that can be written using templates and general knowledge\n"
        f"- Simple professional correspondence\n"
        f"- Any email that doesn't explicitly require current/recent external information\n\n"
        f"Examples:\n"
        f"- 'Write an email to thank a client' → NO (simple thank you, no external info needed)\n"
        f"- 'Write an email about the latest news from Microsoft' → YES (needs recent news)\n"
        f"- 'Confirm the meeting on Monday' → NO (simple confirmation)\n"
        f"- 'Email about current market trends' → YES (needs current market data)\n\n"
        f"Based on the user request above, respond with ONLY 'YES' or 'NO' (no explanation)."
    )
    
    try:
        # Use LLM to intelligently decide if web search is needed
        if llm:
            # Use lower temperature for more consistent, conservative decisions
            # Get model name from llm object
            model_name = "gpt-4o-mini"  # default
            if hasattr(llm, 'model_name'):
                model_name = llm.model_name
            elif hasattr(llm, 'model'):
                model_name = llm.model
            elif hasattr(llm, '_default_params') and 'model' in llm._default_params:
                model_name = llm._default_params['model']
            
            from langchain_openai import ChatOpenAI
            decision_llm = ChatOpenAI(model=model_name, temperature=0.1)
            response = decision_llm.invoke(web_search_prompt).content.strip().upper()
            
            # Be very strict: only YES if explicitly stated, default to NO
            # Check for explicit YES, but also check for NO to be sure
            has_yes = "YES" in response or "OUI" in response
            has_no = "NO" in response or "NON" in response
            
            # Only do web search if YES is explicitly stated AND NO is not present
            needs_web_search = has_yes and not has_no
        else:
            # Fallback: conservative approach - no search by default if no LLM available
            needs_web_search = False
    except Exception as e:
        print(f"⚠️  Error determining web search need: {e}")
        # Fallback: conservative approach - no search by default
        needs_web_search = False
    
    return {
        "retrieved_docs": docs,
        "context": retrieved_content,
        "needs_web_search": needs_web_search,
        "history": state.get("history", []) + ["Retrieved context from vector DB"]
    }

def web_search_node(state: EmailAgentState, search_tool, llm: "ChatOpenAI" = None) -> Dict[str, Any]:
    """Perform web search to enhance context."""
    user_input = state.get("user_input", "")
    context = state.get("context", "")
    
    # Let LLM generate an optimal search query for Tavily
    if llm:
        # Use current date in the instruction to help the model reason about recency
        today_str = datetime.now().strftime("%B %Y")  # e.g. "November 2025"
        search_query_prompt = (
            f"Today's date is {today_str}.\n\n"
            f"Based on this email request, generate an optimal web search query for finding recent, relevant information.\n\n"
            f"User request: {user_input}\n\n"
            f"Generate a search query that will find:\n"
            f"- Recent news or current information (from roughly the last 6–12 months)\n"
            f"- Specific and relevant details\n"
            f"- Up-to-date facts\n\n"
            f"Make the query concise but specific. Include:\n"
            f"- Key entity names (companies, people, products)\n"
            f"- Important keywords\n"
            f"- Words like 'latest', 'recent', 'current' if helpful\n"
            f"- DO NOT include any explicit year (no 2023, 2024, 2025, etc.)\n\n"
            f"Example: If request is 'email about Meta company news', a good query is: Meta company latest news\n\n"
            f"Respond with ONLY the search query (no explanation, no quotes, just the query text)."
        )
        
        try:
            raw_query = llm.invoke(search_query_prompt).content.strip()
            # Clean up the query (remove quotes and explicit years if present)
            search_query = raw_query.strip('"\'')

            # Post-process: remove any explicit four-digit years starting with 20xx
            import re
            search_query = re.sub(r"\b20[0-9]{2}\b", "", search_query)
            # Normalize spaces
            search_query = " ".join(search_query.split())
            print(f"🔍 LLM-generated search query: {search_query}")
        except Exception as e:
            print(f"⚠️  Error generating search query: {e}")
            search_query = user_input  # Fallback to user input
    else:
        search_query = user_input  # Fallback if no LLM
    
    # Perform search (minimal logging, detailed traces go to Langfuse)
    try:
        if search_tool:
            results = search_tool.invoke({"query": search_query})
            # Format results with more content
            if isinstance(results, list):
                web_info = "\n\n".join([
                    f"Source: {r.get('url', 'N/A')}\nTitle: {r.get('title', 'N/A')}\nContent: {r.get('content', '')[:800]}"
                    for r in results[:3]
                ])
            else:
                web_info = str(results)
        else:
            web_info = "Web search tool not available."
            results = []
    except Exception as e:
        print(f"⚠️  Web search error: {e}")
        web_info = ""
        results = []
    
    # Enhance context
    enhanced_context = f"{context}\n\n--- External Information ---\n{web_info}"
    
    return {
        "web_results": results if isinstance(results, list) else [],
        "enhanced_context": enhanced_context,
        "history": state.get("history", []) + ["Performed web search"]
    }

def drafter_node(state: EmailAgentState, llm: "ChatOpenAI") -> Dict[str, Any]:
    """Draft the email or summary based on intent."""
    intent = state.get("intent", "NEW_EMAIL")
    user_input = state.get("user_input", "")
    context = state.get("enhanced_context") or state.get("context", "")
    thread_id = state.get("thread_id")
    
    # Build prompt based on intent
    if intent == "REPLY_EMAIL":
        prompt = (
            f"Based on the following context, write a professional email reply.\n\n"
            f"User instruction: {user_input}\n\n"
            f"Context from previous emails and documents:\n{context}\n\n"
            f"Write a professional, concise email reply. Include:\n"
            f"- Appropriate greeting\n"
            f"- Response to the key points\n"
            f"- Professional closing\n"
            f"Email reply:"
        )
    elif intent == "SUMMARIZE_THREAD":
        prompt = (
            f"Summarize the following email conversation/thread in a clear, structured way.\n\n"
            f"Context:\n{context}\n\n"
            f"Provide a summary that includes:\n"
            f"- Main topics discussed\n"
            f"- Key decisions or actions\n"
            f"- Important dates or deadlines\n"
            f"- Next steps if mentioned\n\n"
            f"Summary:"
        )
    else:  # NEW_EMAIL
        # Check if we have web search results (enhanced_context contains external info)
        has_web_info = "--- External Information ---" in context or state.get("web_results")
        
        if has_web_info:
            prompt = (
                f"Write a professional email based on the following instruction and context.\n\n"
                f"User instruction: {user_input}\n\n"
                f"IMPORTANT: The context below includes EXTERNAL INFORMATION from web search (marked with '--- External Information ---'). "
                f"You MUST use this external information to provide specific, current, and accurate details in the email.\n\n"
                f"Full context (internal documents + external information):\n{context}\n\n"
                f"Write a complete professional email. Format it EXACTLY as follows:\n\n"
                f"Subject: [Your subject line here]\n\n"
                f"[Email body here]\n\n"
                f"CRITICAL REQUIREMENTS:\n"
                f"- Use the EXTERNAL INFORMATION from web search to provide SPECIFIC and CURRENT details\n"
                f"- Include concrete facts, recent news, or current information from the web search results\n"
                f"- Do NOT write generic content - use the actual information found\n"
                f"- Start with 'Subject:' on its own line\n"
                f"- Then a blank line\n"
                f"- Then the email body with specific information from the web search\n"
                f"- Use actual names instead of placeholders when possible\n"
                f"- Keep the email concise but informative\n"
                f"- Include appropriate greeting and closing\n\n"
                f"Email:"
            )
        else:
            prompt = (
                f"Write a professional email based on the following instruction and context.\n\n"
                f"User instruction: {user_input}\n\n"
                f"Context from internal documents and templates:\n{context}\n\n"
                f"Write a complete professional email. Format it EXACTLY as follows:\n\n"
                f"Subject: [Your subject line here]\n\n"
                f"[Email body here]\n\n"
                f"Important:\n"
                f"- Start with 'Subject:' on its own line\n"
                f"- Then a blank line\n"
                f"- Then the email body\n"
                f"- Use actual names instead of placeholders when possible\n"
                f"- If you must use placeholders, use simple ones like 'Client' or 'Team'\n"
                f"- Keep the email concise and professional\n"
                f"- Include appropriate greeting and closing\n\n"
                f"Email:"
            )
    
    draft = llm.invoke(prompt).content.strip()
    
    # Extract subject and body if present
    subject = None
    body = draft
    
    if "Subject:" in draft:
        parts = draft.split("Subject:", 1)
        if len(parts) > 1:
            subject_line = parts[1].split("\n", 1)[0].strip()
            body = parts[1].split("\n", 1)[1].strip() if len(parts[1].split("\n", 1)) > 1 else ""
            subject = subject_line
    
    # Extract metadata (subject, etc.)
    metadata = {
        "intent": intent,
        "thread_id": thread_id,
        "draft_length": len(draft),
        "subject": subject
    }
    
    # Store formatted draft with subject separated
    formatted_draft = draft
    if subject:
        formatted_draft = f"Subject: {subject}\n\n{body}"
    
    return {
        "draft": formatted_draft,
        "draft_metadata": metadata,
        "history": state.get("history", []) + [f"Drafted {intent}"]
    }

def reviewer_node(state: EmailAgentState, llm: "ChatOpenAI") -> Dict[str, Any]:
    """Review the draft for quality, safety, and compliance."""
    draft = state.get("draft", "")
    intent = state.get("intent", "NEW_EMAIL")
    user_input = state.get("user_input", "")
    
    prompt = (
        f"Review the following email draft for quality, professionalism, and compliance.\n\n"
        f"Original user request: {user_input}\n"
        f"Intent: {intent}\n\n"
        f"Draft to review:\n{draft}\n\n"
        f"Check for:\n"
        f"1. Professional tone and appropriate language\n"
        f"2. Coherence with the user's request\n"
        f"3. Absence of grammatical or spelling errors\n"
        f"4. Appropriate length and structure\n"
        f"5. No sensitive information that shouldn't be shared\n\n"
        f"Respond with:\n"
        f"APPROVED: [yes/no]\n"
        f"ISSUES: [list any issues found, or 'none']\n"
        f"SUGGESTIONS: [suggestions for improvement, or 'none']\n"
    )
    
    response = llm.invoke(prompt).content
    
    # Parse response
    approved = "APPROVED: yes" in response.upper() or "APPROVED:true" in response.upper()
    
    issues = []
    suggestions = []
    
    if "ISSUES:" in response:
        issues_section = response.split("ISSUES:")[1].split("SUGGESTIONS:")[0].strip()
        if issues_section.lower() != "none":
            issues = [i.strip() for i in issues_section.split("\n") if i.strip()]
    
    if "SUGGESTIONS:" in response:
        suggestions_section = response.split("SUGGESTIONS:")[1].strip()
        if suggestions_section.lower() != "none":
            suggestions = [s.strip() for s in suggestions_section.split("\n") if s.strip()]
    
    # If not approved and no issues found, approve anyway (to avoid loops)
    if not approved and len(issues) == 0:
        approved = True
        issues = ["Minor review - approved with suggestions"]
    
    return {
        "review_approved": approved,
        "review_issues": issues,
        "review_suggestions": suggestions,
        "history": state.get("history", []) + [f"Review: {'Approved' if approved else 'Needs revision'}"]
    }

# --- Workflow Builder --------------------------------------------------

def build_workflow(llm: "ChatOpenAI", vector_store=None, search_tool=None) -> StateGraph:
    """Build the LangGraph workflow for the email automation agent."""
    workflow = StateGraph(EmailAgentState)
    
    # Define node wrappers
    def _intent_classifier(state: EmailAgentState):
        return intent_classifier_node(state, llm)
    
    def _retrieval(state: EmailAgentState):
        return retrieval_node(state, vector_store, llm)
    
    def _web_search(state: EmailAgentState):
        return web_search_node(state, search_tool, llm)
    
    def _drafter(state: EmailAgentState):
        return drafter_node(state, llm)
    
    def _reviewer(state: EmailAgentState):
        return reviewer_node(state, llm)
    
    # Add nodes
    workflow.add_node("intent_classifier", _intent_classifier)
    workflow.add_node("retrieval", _retrieval)
    workflow.add_node("web_search", _web_search)
    workflow.add_node("drafter", _drafter)
    workflow.add_node("reviewer", _reviewer)
    
    # Set entry point
    workflow.set_entry_point("intent_classifier")
    
    # Add edges
    workflow.add_edge("intent_classifier", "retrieval")
    
    # Conditional: web search if needed
    def route_after_retrieval(state: EmailAgentState) -> str:
        if state.get("needs_web_search", False):
            return "web_search"
        return "drafter"
    
    workflow.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "web_search": "web_search",
            "drafter": "drafter"
        }
    )
    
    workflow.add_edge("web_search", "drafter")
    workflow.add_edge("drafter", "reviewer")
    
    # Conditional: reviewer approval
    def route_after_review(state: EmailAgentState) -> str:
        if state.get("review_approved", False):
            return "end"
        return "drafter"  # Loop back to drafter with feedback
    
    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "end": END,
            "drafter": "drafter"
        }
    )
    
    return workflow

# --- Checkpointer Loader -----------------------------------------------

@contextmanager
def get_checkpointer(db_path: str):
    """
    Yield a real checkpointer object. If SQLite is available, open it;
    otherwise yield MemorySaver. This function itself is the only
    context manager.
    """
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        with SqliteSaver.from_conn_string(db_path) as mem:
            yield mem
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver
        mem = MemorySaver()
        print("⚠️  SQLite unavailable; using in-memory saver.")
        # No close needed for MemorySaver
        yield mem

