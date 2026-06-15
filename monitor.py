#!/usr/bin/env python3
"""
JustPark FIFA World Cup Parking Monitor — Playwright version
Renders the full JS page for July 19th and checks if "Sold Out" changes
to anything else (e.g. "Add to Cart", "Buy Now", a price, etc.)
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

# This URL opens the page with July 19th already selected
URL = "https://www.justpark.com/us/event-parking/fifa-world-cup-2026/new-york-new-jersey-stadium/"

TARGET_DATE  = "july 19"          # text to confirm we're on the right event
STATE_FILE   = "state.json"

EMAIL_SENDER    = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD  = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]

# ─────────────────────────────────────────────


def get_parking_status() -> dict:
    """Use Playwright to render the page and extract July 19 availability."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page.goto(URL, wait_until="networkidle", timeout=30000)

        # Click on the July 19 event if a calendar/event list is present
        try:
            page.get_by_text("7/19", exact=False).first.click(timeout=5000)
            page.wait_for_timeout(2000)
        except Exception:
            pass  # might already be selected or text differs

        # Grab the full rendered text
        content = page.inner_text("body").lower()
        browser.close()

    # Find all lines that contain "sold out", "available", "add to cart",
    # prices ($), or July 19 references
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    relevant = [
        l for l in lines if any(kw in l for kw in [
            "sold out", "available", "add to cart", "buy now",
            "general pricing", "ada", "parking", "july 19", "7/19",
            "$", "select", "waitlist"
        ])
    ]

    # Build a status snapshot
    status = {
        "july_19_found":   "july 19" in content or "7/19" in content,
        "sold_out":        "sold out" in content,
        "available":       "available" in content and "sold out" not in content,
        "add_to_cart":     "add to cart" in content,
        "relevant_lines":  relevant[:30],   # cap at 30 lines
        "checked_at":      datetime.now().isoformat(),
    }
    return status


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_email(old: dict, new: dict) -> None:
    subject = "🚨 FIFA World Cup Final Parking — July 19 Status Changed!"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Highlight key changes
    changes = []
    for key in ["sold_out", "available", "add_to_cart"]:
        if old.get(key) != new.get(key):
            changes.append(f"  {key}: {old.get(key)} → {new.get(key)}")

    old_lines = set(old.get("relevant_lines", []))
    new_lines  = set(new.get("relevant_lines", []))
    added   = new_lines - old_lines
    removed = old_lines - new_lines

    body = f"""
A change was detected on the JustPark FIFA World Cup parking page for July 19th!

Detected at: {timestamp}
Page: {URL}

KEY STATUS CHANGES:
{chr(10).join(changes) if changes else '  (see page text changes below)'}

NEW TEXT ON PAGE:
{chr(10).join(f'  + {l}' for l in sorted(added)) or '  (none)'}

REMOVED TEXT FROM PAGE:
{chr(10).join(f'  - {l}' for l in sorted(removed)) or '  (none)'}

CURRENT PAGE STATUS:
  July 19 found: {new.get('july_19_found')}
  Sold Out:      {new.get('sold_out')}
  Available:     {new.get('available')}
  Add to Cart:   {new.get('add_to_cart')}

➡ CHECK NOW: {URL}
"""

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

    print(f"  ✉  Alert sent to {EMAIL_RECIPIENT}")


def main() -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking July 19 parking status...")

    try:
        current = get_parking_status()
    except Exception as e:
        print(f"  ✗  Failed to fetch page: {e}")
        return

    print(f"  July 19 found: {current['july_19_found']}")
    print(f"  Sold Out:      {current['sold_out']}")
    print(f"  Available:     {current['available']}")
    print(f"  Add to Cart:   {current['add_to_cart']}")
    print(f"  Relevant lines: {current['relevant_lines'][:5]}")

    state = load_state()
    previous = state.get("status")

    # Compare only the stable keys (not checked_at)
    def comparable(s):
        return {k: v for k, v in s.items() if k != "checked_at"} if s else {}

    if previous is None:
        print("  ✓  First run — baseline saved.")
    elif comparable(previous) == comparable(current):
        print("  ✓  No change detected.")
    else:
        print("  ⚠  Change detected! Sending alert...")
        try:
            send_email(previous, current)
        except Exception as e:
            print(f"  ✗  Email failed: {e}")

    state["status"] = current
    save_state(state)


if __name__ == "__main__":
    main()
