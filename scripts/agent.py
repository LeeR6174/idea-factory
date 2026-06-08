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
    
    Please analyze the repository, write or modify the necessary code to solve this issue.
    Use your built-in tools to read files, create new files, or edit existing files as needed.
    Once you have made the necessary changes, provide a brief summary of what you did.
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
