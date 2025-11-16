# email_agent_chat.py
"""
Interactive chat interface for the persistent email automation agent.
"""

import os
import uuid
import argparse
from src.build_agent import build_email_agent
from src.utils import get_checkpointer, reviewer_node

HELP = """
Commands:
  /new <instruction>    Start a new email task (e.g., "Reply to this email")
  /resume               Resume from last checkpoint
  /show                 Show current progress and draft
  /approve              Approve the current draft
  /edit <text>          Edit the draft with new text
  /id                   Show current thread_id
  /intent               Show detected intent
  /help                 Show this help
  /exit                 Quit
"""

def print_state(app, config):
    """Pretty-print current state snapshot."""
    snap = app.get_state(config)
    if not snap:
        print("No saved state yet for this thread.")
        return
    values = getattr(snap, "values", snap)
    
    # Show intent (without confidence for simpler output)
    if "intent" in values and values["intent"]:
        print(f"\n[INTENT] {values['intent']}")
    
    # Show draft with better formatting
    if "draft" in values and values["draft"]:
        draft = values["draft"]
        # Check if subject is separate
        if "Subject:" in draft and "\n\n" in draft:
            parts = draft.split("\n\n", 1)
            if len(parts) == 2 and parts[0].startswith("Subject:"):
                subject = parts[0].replace("Subject:", "").strip()
                body = parts[1]
                print(f"\n[SUBJECT]\n{subject}")
                print(f"\n[BODY]\n{body}")
            else:
                print(f"\n[DRAFT]\n{draft}")
        else:
            print(f"\n[DRAFT]\n{draft}")
    
    # Show review status
    if "review_approved" in values:
        status = "✅ Approved" if values["review_approved"] else "❌ Needs revision"
        print(f"\n[REVIEW STATUS] {status}")
        if values.get("review_issues"):
            print(f"Issues: {', '.join(values['review_issues'])}")
        if values.get("review_suggestions"):
            print(f"Suggestions: {', '.join(values['review_suggestions'])}")
    
    # Show history
    if "history" in values and values["history"]:
        print(f"\n[HISTORY]")
        print(" -> ".join(values["history"][-5:]))  # Show last 5 steps
    
    # Show available next actions
    print(f"\n[AVAILABLE ACTIONS]")
    has_draft = "draft" in values and values.get("draft")
    is_approved = values.get("review_approved", False)
    
    if has_draft:
        if is_approved:
            print("  ✅ /approve  - Approve and finalize the email")
            print("  ✏️  /edit <text>  - Edit the draft before approving")
        else:
            print("  ⏭️  /resume  - Continue processing (review will run)")
            print("  ✏️  /edit <text>  - Edit the draft")
    else:
        print("  ⏭️  /resume  - Continue processing")
    
    print("  🔄 /new <instruction>  - Start a new email task")
    print("  📋 /show  - Show current state again")
    print("  🆔 /id  - Show thread ID")
    print("  ❓ /help  - Show all commands")
    print("  🚪 /exit  - Quit")

def run_chat(app, db_path: str, llm, langfuse_handler=None):
    """Main REPL loop."""
    print("\n✅ Email automation agent ready.")
    print(f"Persistence DB: {db_path}")
    print(HELP)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
    current_input = None

    print(f"\nCurrent thread_id: {thread_id}")
    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not cmd:
            continue
        if cmd == "/exit":
            break
        if cmd == "/help":
            print(HELP)
            continue
        if cmd == "/id":
            print(f"thread_id: {thread_id}")
            continue
        if cmd == "/intent":
            snap = app.get_state(config)
            if snap:
                values = getattr(snap, "values", snap)
                intent = values.get("intent", "Not classified yet")
                confidence = values.get("intent_confidence", 0)
                print(f"Intent: {intent} (confidence: {confidence:.2f})")
            else:
                print("No state yet. Start with /new")
            continue
        if cmd == "/show":
            print_state(app, config)
            continue

        if cmd.startswith("/new "):
            current_input = cmd[5:].strip()
            if not current_input:
                print("Usage: /new <instruction>")
                print("Example: /new Reply to this email confirming the meeting")
                continue
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            print(f"🆕 New thread started ({thread_id})")
            print(f"📝 Processing: {current_input}")
            
            # Invoke with user input
            try:
                invoke_config = config.copy()
                if langfuse_handler:
                    invoke_config["callbacks"] = [langfuse_handler]
                result = app.invoke(
                    {"user_input": current_input, "history": [], "step_count": 0},
                    config=invoke_config
                )
                print("\n⏸️  Paused for human review. Use /show to see the draft, then /approve or /edit")
            except Exception as e:
                print(f"❌ Error: {e}")
            continue

        if cmd == "/resume":
            try:
                invoke_config = config.copy()
                if langfuse_handler:
                    invoke_config["callbacks"] = [langfuse_handler]
                result = app.invoke(None, config=invoke_config)
                snap = app.get_state(config)
                if snap:
                    values = getattr(snap, "values", snap)
                    if values.get("review_approved") and values.get("draft"):
                        print("\n✅ Draft approved! Use /show to see the final email.")
                    elif values.get("draft"):
                        print("\n⏸️  Still paused. Use /show to see the draft, then /approve or /edit")
                    else:
                        print("\n⏸️  Processing... Use /show to see progress.")
                else:
                    print("No state to resume. Start with /new")
            except Exception as e:
                print(f"❌ Error: {e}")
            continue

        if cmd == "/approve":
            snap = app.get_state(config)
            if not snap:
                print("No draft to approve. Start with /new")
                continue
            values = getattr(snap, "values", snap)
            if not values.get("draft"):
                print("No draft available. Use /show to check status.")
                continue
            
            # Update state to mark as approved
            print("\n✅ Draft approved!")
            print(f"\n[FINAL EMAIL]\n{values['draft']}")
            print("\n💡 In a real system, this email would be sent now.")
            
            # Optionally update state
            try:
                app.update_state(
                    config,
                    {"human_approved": True, "final_email": values["draft"]}
                )
            except Exception as e:
                print(f"Note: Could not update state ({e})")
            continue

        if cmd.startswith("/edit "):
            new_text = cmd[6:].strip()
            if not new_text:
                print("Usage: /edit <new draft text>")
                continue
            snap = app.get_state(config)
            if not snap:
                print("No draft to edit. Start with /new")
                continue
            
            # Update draft with new text
            try:
                app.update_state(
                    config,
                    {"draft": new_text, "human_feedback": "User edited draft"}
                )
                print("✅ Draft updated. Re-running review on edited draft...")

                # Re-run reviewer on the updated draft so [REVIEW STATUS] is refreshed
                snap = app.get_state(config)
                values = getattr(snap, "values", snap)
                review_update = reviewer_node(values, llm)
                app.update_state(config, review_update)
                print("🔁 Review updated. Use /show to see the new [REVIEW STATUS].")
            except Exception as e:
                print(f"❌ Error updating draft or review: {e}")
            continue

        print("Unknown command. Type /help for help.")

def main():
    parser = argparse.ArgumentParser(description="Email Automation Agent CLI")
    parser.add_argument("--db", default="email_agent.db", help="SQLite database path")
    parser.add_argument("--vector-db", default="./chroma_db", help="ChromaDB directory")
    parser.add_argument("--vector-data", default="vector_data", help="Vector data directory")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model to use")
    parser.add_argument("--fresh", action="store_true", help="Start with fresh database")
    parser.add_argument("--no-langfuse", action="store_true", help="Disable Langfuse monitoring")
    args = parser.parse_args()

    if args.fresh and os.path.exists(args.db):
        os.remove(args.db)
        print(f"🗑️  Removed old DB: {args.db}")

    # Build workflow components
    try:
        workflow, llm, vector_store, search_tool, langfuse_handler = build_email_agent(
            db_path=args.db,
            vector_db_path=args.vector_db,
            vector_data_dir=args.vector_data,
            model=args.model,
            enable_langfuse=not args.no_langfuse
        )
        
        # Compile and run chat interface (with checkpointer in context)
        with get_checkpointer(args.db) as checkpointer:
            agent = workflow.compile(
                checkpointer=checkpointer,
                interrupt_after=["reviewer"]  # Show review status before human approval
            )
            # Store langfuse_handler and llm for use in run_chat
            run_chat(agent, args.db, llm, langfuse_handler)
        
    except Exception as e:
        print(f"❌ Error building agent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

