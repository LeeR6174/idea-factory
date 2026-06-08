import asyncio
import os
import sys
import re
import json
from datetime import datetime
from google.antigravity import Agent, LocalAgentConfig

def slugify(text):
    # Keep alphanumeric characters and Japanese characters (Hiragana, Katakana, Kanji)
    # Replace spaces and hyphens with a single hyphen
    text = re.sub(r'[^\w\s\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf-]', '', text)
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text

async def main():
    # GitHub Actions sets these environment variables
    issue_title = os.environ.get("ISSUE_TITLE", "")
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "unknown")

    if not issue_title:
        print("No ISSUE_TITLE provided. Exiting.")
        sys.exit(1)

    try:
        issue_idx = int(issue_number)
        folder_name = f"{issue_idx:03d}-{slugify(issue_title)}"
    except ValueError:
        folder_name = f"unknown-{slugify(issue_title)}"

    apps_dir = f"apps/{folder_name}"
    print(f"Processing Issue #{issue_number}: {issue_title}")
    print(f"Target Directory: {apps_dir}")

    # Initialize the Antigravity Agent Configuration
    config = LocalAgentConfig()
    
    # Formulate the prompt for the agent
    prompt = f"""
    You are an autonomous AI developer working on this repository.
    A new issue has been created:
    
    TITLE: {issue_title}
    BODY: {issue_body}
    
    CRITICAL INSTRUCTION: You must implement this application as a PURE client-side static web application (HTML, CSS, JavaScript).
    - Do NOT write any backend server code (no Python, no Node.js server, no SQLite database).
    - Save all data in the browser using `localStorage` or `indexedDB`.
    - Create ALL files inside the specific directory: `{apps_dir}` (e.g. `{apps_dir}/index.html`, `{apps_dir}/style.css`, `{apps_dir}/script.js` etc.)
    - Do not read or write files outside this directory.
    - Write the files in a SINGLE tool call if possible, or at most 2 tool calls, due to strict API limits.
    
    Please create a modern, beautiful, and fully functional app in `{apps_dir}` based on the issue description.
    Once completed, provide a brief summary of what you did.
    """

    # Run the agent
    agent_success = False
    agent_summary = ""
    try:
        async with Agent(config) as agent:
            print("Starting agent...")
            response = await agent.chat(prompt)
            print("\n--- Agent Execution Complete ---")
            agent_summary = await response.text()
            print("Agent Summary:")
            print(agent_summary)
            agent_success = True
    except Exception as e:
        print(f"Error executing agent: {e}")
        sys.exit(1)

    # If successful, register the app in apps.json
    if agent_success:
        apps_json_path = "apps.json"
        
        # Extract a short description from the issue body
        short_desc = issue_body.split('\n')[0][:120].strip() if issue_body else "No description provided."
        
        new_app = {
            "id": f"{int(issue_number):03d}" if issue_number.isdigit() else issue_number,
            "title": issue_title,
            "description": short_desc,
            "path": f"apps/{folder_name}",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        apps_list = []
        if os.path.exists(apps_json_path):
            try:
                with open(apps_json_path, "r", encoding="utf-8") as f:
                    apps_list = json.load(f)
            except Exception as e:
                print(f"Warning: could not parse existing apps.json: {e}")
                
        # Check if already registered
        exists = any(app["id"] == new_app["id"] for app in apps_list)
        if not exists:
            apps_list.append(new_app)
            # Sort by id descending (newest first)
            apps_list.sort(key=lambda x: x["id"], reverse=True)
            with open(apps_json_path, "w", encoding="utf-8") as f:
                json.dump(apps_list, f, ensure_ascii=False, indent=2)
            print(f"Successfully registered '{issue_title}' in {apps_json_path}")
        else:
            print(f"App with ID {new_app['id']} is already registered in {apps_json_path}")

if __name__ == "__main__":
    asyncio.run(main())
