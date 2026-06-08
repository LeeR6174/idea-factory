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
    
    CRITICAL INSTRUCTION: You must implement this application as a PURE client-side static web application (HTML, CSS, JavaScript) that fully supports PWA (Progressive Web App) specifications so it can be installed on mobile devices.
    - Do NOT write any backend server code (no Python, no Node.js server, no SQLite database).
    - Save all data in the browser using `localStorage` or `indexedDB`.
    - Create ALL files inside the specific directory: `{apps_dir}` (e.g. `{apps_dir}/index.html`, `{apps_dir}/manifest.json`, `{apps_dir}/service-worker.js` etc.)
    - Do not read or write files outside this directory.
    - Write the files in a SINGLE tool call if possible, or at most 2 tool calls, due to strict API limits.
    - **PWA Requirements**:
      1. Create a `manifest.json` containing: `name`, `short_name`, `start_url` (must be `./index.html`), `display` ("standalone"), `background_color`, `theme_color`, and a reference to icons `./icon-192.png` and `./icon-512.png` (these icons will be provisioned automatically, so just reference them in the manifest).
      2. Create a basic `service-worker.js` that implements a caching strategy (e.g. Cache First or Stale-While-Revalidate) for the app's local files (like `index.html`, `manifest.json`, and any external libraries if used).
      3. In `index.html`, add `<link rel="manifest" href="manifest.json">`, standard mobile viewport configurations (including `viewport-fit=cover`), Apple mobile web app meta tags (`apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`), and Javascript code to register `./service-worker.js` on load.
    
    DESIGN SYSTEM INSTRUCTION (Apple Style):
    You must strictly follow the Apple design system guidelines (summarized below, full spec in `DESIGNS/DESIGN-apple.md`):
    - Color Palette: Use a clean white (`#ffffff`) and parchment off-white (`#f5f5f7`) background. The ONLY interactive/accent color is Action Blue (`#0066cc`). For text, use Near-Black Ink (`#1d1d1f`) and muted text (`#86868b`).
    - Typography: Use `Inter` or system-ui fonts. Display headers should have negative letter-spacing (`letter-spacing: -0.015em` to `-0.02em`) and weight 600.
    - Grid & Spacing: Low density, clean spacing. Space things out generously.
    - Elevation & Shadows: Flat design. Do NOT use drop-shadows on cards, buttons, or text. Use borders (`1px solid #e5e5e7`) and background color changes for separation.
    - Shapes & Radius: Use 9999px pill shape (`border-radius: 9999px`) for primary action buttons and search inputs. Use 18px (`border-radius: 18px`) for content cards, and 8px (`border-radius: 8px`) for smaller inputs.
    
    Please create a modern, beautiful, and fully functional app in `{apps_dir}` based on the issue description and design rules.
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
        # Copy default PWA icons to the new app directory
        import shutil
        for icon_name in ["icon-192.png", "icon-512.png"]:
            src_icon = icon_name
            dst_icon = os.path.join(apps_dir, icon_name)
            if os.path.exists(src_icon):
                try:
                    shutil.copy(src_icon, dst_icon)
                    print(f"Copied PWA icon {src_icon} to {dst_icon}")
                except Exception as e:
                    print(f"Warning: could not copy icon {src_icon}: {e}")

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
