import asyncio
import os
import sys
import re
import json
import subprocess
import time
from datetime import datetime, timezone
from google.antigravity import Agent, LocalAgentConfig

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Global counters
_api_call_count = 0
_start_time: float = 0.0


def log(level: str, message: str) -> None:
    """Structured log output with timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [{level}] {message}", flush=True)


def log_info(message: str) -> None:
    log("INFO", message)


def log_warn(message: str) -> None:
    log("WARN", message)


def log_error(message: str) -> None:
    log("ERROR", message)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Keep alphanumeric and CJK characters; replace spaces/hyphens with '-'."""
    text = re.sub(r'[^\w\s\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf-]', '', text)
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text


# ---------------------------------------------------------------------------
# GitHub Issue comment
# ---------------------------------------------------------------------------

def post_issue_comment(issue_number: str, body: str) -> None:
    """Post a comment to the GitHub Issue using the GitHub CLI."""
    gh_token = os.environ.get("GH_TOKEN", "")
    if not gh_token:
        log_warn("GH_TOKEN not set – skipping Issue comment.")
        return
    try:
        result = subprocess.run(
            ["gh", "issue", "comment", issue_number, "--body", body],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            log_info(f"Posted error comment to Issue #{issue_number}")
        else:
            log_warn(f"gh issue comment failed: {result.stderr.strip()}")
    except Exception as exc:
        log_warn(f"Could not post Issue comment: {exc}")


def _build_error_comment(error_type: str, detail: str, issue_number: str) -> str:
    messages = {
        "rate_limit": (
            "## ⚠️ Gemini API レート制限エラー\n\n"
            "Gemini API のレート制限 (HTTP 429) に達したため、Agent 処理が停止しました。\n\n"
            f"**詳細:** `{detail}`\n\n"
            "**対処法:** しばらく待ってから、このワークフローを再実行してください。"
        ),
        "overload": (
            "## ⚠️ Gemini API 過負荷エラー\n\n"
            "Gemini API が現在混雑しています (HTTP 503)。Agent 処理が停止しました。\n\n"
            f"**詳細:** `{detail}`\n\n"
            "**対処法:** 数分後にワークフローを再実行してください。"
        ),
        "generic": (
            "## ❌ Agent 処理エラー\n\n"
            f"Issue #{issue_number} の処理中にエラーが発生しました。\n\n"
            f"**詳細:** `{detail}`\n\n"
            "**対処法:** GitHub Actions のログを確認し、必要に応じてワークフローを再実行してください。"
        ),
    }
    return messages.get(error_type, messages["generic"])


# ---------------------------------------------------------------------------
# Agent call with retry / backoff
# ---------------------------------------------------------------------------

async def call_agent_with_retry(
    config: LocalAgentConfig,
    prompt: str,
    issue_number: str,
    max_retries: int = 3,
) -> str:
    """
    Call Agent.chat() with exponential backoff retry on 429 / 503 errors.

    Returns the agent response text on success.
    Raises the last exception after all retries are exhausted.
    """
    global _api_call_count

    # Backoff schedule (seconds): 15 → 30 → 60
    backoff_schedule = [15, 30, 60]

    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        call_start = time.monotonic()
        _api_call_count += 1
        log_info(
            f"API call #{_api_call_count} – attempt {attempt}/{max_retries} "
            f"(Issue #{issue_number})"
        )

        try:
            async with Agent(config) as agent:
                response = await agent.chat(prompt)
                elapsed = time.monotonic() - call_start
                log_info(
                    f"API call #{_api_call_count} completed in {elapsed:.1f}s "
                    f"(attempt {attempt}/{max_retries})"
                )
                return await response.text()

        except Exception as exc:
            elapsed = time.monotonic() - call_start
            exc_str = str(exc)
            last_exception = exc

            # Classify error
            is_rate_limit = "429" in exc_str or "quota" in exc_str.lower() or "rate" in exc_str.lower()
            is_overload   = "503" in exc_str or "overloaded" in exc_str.lower() or "unavailable" in exc_str.lower()

            if is_rate_limit:
                error_type = "rate_limit"
                label = "HTTP 429 (Rate Limit)"
            elif is_overload:
                error_type = "overload"
                label = "HTTP 503 (Service Overloaded)"
            else:
                error_type = "generic"
                label = "Unexpected error"

            log_error(
                f"API call #{_api_call_count} failed after {elapsed:.1f}s – "
                f"{label}: {exc_str[:200]}"
            )

            if attempt < max_retries:
                wait_sec = backoff_schedule[attempt - 1]
                log_warn(f"Retrying in {wait_sec}s… ({attempt}/{max_retries})")
                await asyncio.sleep(wait_sec)
            else:
                log_error(f"All {max_retries} attempts failed. Giving up.")
                # Post to Issue
                comment = _build_error_comment(error_type, exc_str[:500], issue_number)
                post_issue_comment(issue_number, comment)

    raise last_exception


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    global _start_time
    _start_time = time.monotonic()

    # --- Read environment variables ---
    issue_title  = os.environ.get("ISSUE_TITLE", "")
    issue_body   = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "unknown")

    log_info(f"=== Agent started ===")
    log_info(f"Issue #{issue_number}: {issue_title}")

    if not issue_title:
        log_error("No ISSUE_TITLE provided. Exiting.")
        sys.exit(1)

    try:
        issue_idx   = int(issue_number)
        folder_name = f"{issue_idx:03d}-{slugify(issue_title)}"
    except ValueError:
        folder_name = f"unknown-{slugify(issue_title)}"

    apps_dir = f"apps/{folder_name}"
    log_info(f"Target directory: {apps_dir}")

    # --- Build config ---
    config = LocalAgentConfig()

    # --- Build prompt (optimised for minimal API round-trips) ---
    prompt = f"""
You are an autonomous AI developer. Implement the web application described below.
Write ALL required files immediately without any intermediate steps.

DO NOT produce any of the following – they waste API quota and slow down delivery:
- Requirements documents or design specifications
- Architecture planning or pseudocode
- Explanatory text or commentary before writing files
- Code review, reflection, or "what I did" summaries mid-task
- Clarifying questions of any kind

Write every file the app needs, THEN output a short summary. That's it.

Issue details:
  TITLE : {issue_title}
  BODY  : {issue_body}

IMPLEMENTATION REQUIREMENTS
───────────────────────────
1. Pure client-side static web app (HTML + CSS + JavaScript). No backend.
2. All data must be saved using localStorage or indexedDB.
3. Create ALL files inside: `{apps_dir}/`
   Required files: `index.html`, `manifest.json`, `service-worker.js`
4. Icons `./icon-192.png` and `./icon-512.png` will be provisioned automatically –
   just reference them in manifest.json.
5. Do NOT read or write files outside `{apps_dir}/`.

PWA REQUIREMENTS
────────────────
- manifest.json: name, short_name, start_url ("./index.html"), display ("standalone"),
  background_color, theme_color, icons (192px & 512px).
- service-worker.js: Cache-First or Stale-While-Revalidate strategy for local files.
- index.html:
    <link rel="manifest" href="manifest.json">
    Viewport meta with viewport-fit=cover
    Apple mobile web app meta tags
    JS to register ./service-worker.js on load

DESIGN SYSTEM (Apple style)
────────────────────────────
Follow `DESIGNS/DESIGN-apple.md`. Key rules:
- Background: #ffffff / #f5f5f7. Accent: #0066cc only. Text: #1d1d1f / #86868b.
- Font: Inter or system-ui. Headers: font-weight 600, letter-spacing -0.015em to -0.02em.
- No drop-shadows. Use 1px solid #e5e5e7 borders for separation.
- Pill buttons (border-radius: 9999px), card radius 18px, input radius 8px.
- Low density, generous spacing.

OUTPUT
──────
Write all files in one batch, then respond with a brief summary (3-5 sentences) of
what was implemented. Nothing else.
"""

    # --- Run agent with retry ---
    agent_success  = False
    agent_summary  = ""
    try:
        agent_summary = await call_agent_with_retry(
            config=config,
            prompt=prompt,
            issue_number=issue_number,
            max_retries=3,
        )
        log_info("--- Agent execution complete ---")
        log_info(f"Summary: {agent_summary}")
        agent_success = True
    except Exception as exc:
        log_error(f"Agent failed: {exc}")
        # Issue comment was already posted inside call_agent_with_retry
        elapsed_total = time.monotonic() - _start_time
        log_info(f"Total elapsed: {elapsed_total:.1f}s | API calls made: {_api_call_count}")
        sys.exit(1)

    # --- Post-processing on success ---
    if agent_success:
        import shutil

        # Copy default PWA icons
        for icon_name in ["icon-192.png", "icon-512.png"]:
            src_icon = icon_name
            dst_icon = os.path.join(apps_dir, icon_name)
            if os.path.exists(src_icon):
                try:
                    shutil.copy(src_icon, dst_icon)
                    log_info(f"Copied PWA icon: {src_icon} → {dst_icon}")
                except Exception as exc:
                    log_warn(f"Could not copy icon {src_icon}: {exc}")

        # Register app in apps.json
        apps_json_path = "apps.json"
        short_desc = issue_body.split('\n')[0][:120].strip() if issue_body else "No description provided."

        new_app = {
            "id"         : f"{int(issue_number):03d}" if issue_number.isdigit() else issue_number,
            "title"      : issue_title,
            "description": short_desc,
            "path"       : f"apps/{folder_name}",
            "date"       : datetime.now().strftime("%Y-%m-%d"),
        }

        apps_list = []
        if os.path.exists(apps_json_path):
            try:
                with open(apps_json_path, "r", encoding="utf-8") as f:
                    apps_list = json.load(f)
            except Exception as exc:
                log_warn(f"Could not parse existing apps.json: {exc}")

        exists = any(app["id"] == new_app["id"] for app in apps_list)
        if not exists:
            apps_list.append(new_app)
            apps_list.sort(key=lambda x: x["id"], reverse=True)
            with open(apps_json_path, "w", encoding="utf-8") as f:
                json.dump(apps_list, f, ensure_ascii=False, indent=2)
            log_info(f"Registered '{issue_title}' in {apps_json_path}")
        else:
            log_info(f"App ID {new_app['id']} already registered in {apps_json_path}")

    elapsed_total = time.monotonic() - _start_time
    log_info(
        f"=== Agent finished ==="
        f" | elapsed: {elapsed_total:.1f}s"
        f" | total API calls: {_api_call_count}"
    )


if __name__ == "__main__":
    asyncio.run(main())
