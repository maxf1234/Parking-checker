#!/usr/bin/env python3
"""
JustPark FIFA World Cup Parking Monitor — Playwright version
Watches for any sign that July 19th parking has become available.
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

URL        = "https://www.justpark.com/us/event-parking/fifa-world-cup-2026/new-york-new-jersey-stadium/"
STATE_FILE = "state.json"

EMAIL_SENDER    = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD  = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]

# ─────────────────────────────────────────────
# AVAILABILITY TRIGGERS
# Alert fires if ANY of these appear on the page (positive signals)
# ─────────────────────────────────────────────
POSITIVE_TRIGGERS = [
    # Buy actions
    "add to cart",
    "book now",
    "reserve now",
    "purchase now",
    "checkout",
    "proceed to checkout",
    "complete purchase",
    "confirm booking",
    "get tickets",
    "secure your spot",
    "claim your spot",
    "grab your pass",
    "order now",
    "pay now",

    # Availability language
    "spaces available",
    "spots available",
    "passes available",
    "now available",
    "back in stock",
    "newly available",
    "just released",
    "just added",
    "new inventory",
    "inventory added",
    "released",
    "restocked",
    "limited availability",
    "limited spots",
    "limited passes",
    "spots remaining",
    "passes remaining",
    "spaces remaining",
    "only a few left",
    "almost gone",
    "hurry",
    "going fast",
    "selling fast",
    "in stock",
    "1 left",
    "2 left",
    "3 left",

    # Pricing appearing (signals item is purchasable)
    "$25",
    "$30",
    "$35",
    "$40",
    "$45",
    "$50",
    "$55",
    "$60",
    "$65",
    "$70",
    "$75",
    "$80",
    "$85",
    "$90",
    "$95",
    "$100",
    "$110",
    "$120",
    "$125",
    "$150",
    "$175",
    "$200",

    # UI elements that appear when buying is possible
    "select quantity",
    "choose quantity",
    "quantity",
    "continue",
    "next step",
    "payment",
    "enter payment",
    "card number",
    "select parking",
    "choose parking",
    "pick your spot",
    "view passes",
    "view options",
    "see options",
]

# ─────────────────────────────────────────────
# NEGATIVE TRIGGERS
# Alert fires if ANY of these DISAPPEAR from the page
# ─────────────────────────────────────────────
NEGATIVE_TRIGGERS = [
    # Only phrases confirmed present on the page right now
    "sold out",
    "join the waitlist",
    "waitlist",
]


def get_parking_status() -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page.goto(URL, wait_until="networkidle", timeout=30000)

        # Dismiss cookie consent popup if present
        for cookie_selector in [
            "button:has-text('Accept')",
            "button:has-text('Accept all')",
            "button:has-text('Allow all')",
            "button:has-text('OK')",
            "button:has-text('Got it')",
            "[id*='cookie'] button",
            "[class*='cookie'] button",
            "[class*='consent'] button",
        ]:
            try:
                btn = page.locator(cookie_selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(1000)
                    print(f"  Dismissed cookie popup: {cookie_selector}")
                    break
            except Exception:
                continue

        # Click the July 19th event to open its panel
        try:
            page.get_by_text("7/19", exact=False).first.click(timeout=5000)
            page.wait_for_timeout(2000)
        except Exception:
            pass

        # Grab full page and extract a window around the July 19 section
        full = page.inner_text("body").lower()
        browser.close()

    lines = full.splitlines()
    content = None

    # Find the July 19 anchor line and grab 60 lines after it
    for i, line in enumerate(lines):
        if "7/19" in line or "july 19" in line or "match 104" in line:
            start = max(0, i - 3)
            end   = min(len(lines), i + 60)
            content = "\n".join(lines[start:end])
            print(f"  Isolated July 19 section at line {i} ({len(content)} chars)")
            break

    if not content:
        content = full
        print("  Warning: could not find July 19 on page, using full page text")

    print(f"  Scoped content ({len(content)} chars): {content[:300]!r}")

    positive_found = {t: t in content for t in POSITIVE_TRIGGERS}
    negative_found = {t: t in content for t in NEGATIVE_TRIGGERS}

    return {
        "july_19_found":    "july 19" in content or "7/19" in content or "match 104" in content,
        "positive_found":   positive_found,
        "negative_found":   negative_found,
        "checked_at":       datetime.now().isoformat(),
    }


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

    # Positive triggers that newly appeared
    newly_appeared = [
        t for t in POSITIVE_TRIGGERS
        if new["positive_found"].get(t) and not old.get("positive_found", {}).get(t)
    ]
    # Negative triggers that disappeared
    newly_gone = [
        t for t in NEGATIVE_TRIGGERS
        if not new["negative_found"].get(t) and old.get("negative_found", {}).get(t)
    ]

    body = f"""
🚨 A change was detected on the JustPark FIFA World Cup Final parking page!

Detected at: {timestamp}
Page: {URL}

GOOD SIGNS — NOW APPEARING ON PAGE:
{chr(10).join(f'  ✅ "{t}"' for t in newly_appeared) or '  (none)'}

SOLD OUT LANGUAGE — NOW GONE FROM PAGE:
{chr(10).join(f'  ✅ "{t}" disappeared' for t in newly_gone) or '  (none)'}

➡ GO BUY NOW: {URL}
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

    print(f"  July 19 found:    {current['july_19_found']}")
    print(f"  Positive matches: {[t for t, v in current['positive_found'].items() if v]}")
    print(f"  Negative matches: {[t for t, v in current['negative_found'].items() if v]}")

    state  = load_state()
    previous = state.get("status")

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
