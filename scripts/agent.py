import asyncio
import os
import sys
from google.antigravity import Agent, LocalAgentConfig

async def main():
    # GitHub Actions sets these environment variables
    issue_title = os.environ.get("ISSUE_TITLE", "")
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "unknown")

    if not issue_title:
        print("No ISSUE_TITLE provided. Exiting.")
        sys.exit(1)

    print(f"Processing Issue #{issue_number}: {issue_title}")

    # Initialize the Antigravity Agent Configuration
    config = LocalAgentConfig()
    
    # Formulate the prompt for the agent
    prompt = f"""
    You are an autonomous AI developer working on this repository.
    A new issue has been created:
    
    TITLE: {issue_title}
    BODY: {issue_body}
    
    CRITICAL INSTRUCTION: You are operating under a strict API rate limit (maximum 5 API requests per minute).
    You MUST avoid step-by-step exploration. Do NOT read files one by one unless absolutely necessary.
    Instead, plan your solution and use your built-in tools to create or edit the required files in a SINGLE tool call (or 2 at most).
    Complete the task as quickly and efficiently as possible, then provide a brief summary of what you did.
    """

    # Run the agent
    try:
        async with Agent(config) as agent:
            print("Starting agent...")
            response = await agent.chat(prompt)
            print("\n--- Agent Execution Complete ---")
            print("Agent Summary:")
            print(await response.text())
    except Exception as e:
        print(f"Error executing agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
