#!/usr/bin/env python3
"""
JustPark FIFA World Cup Final Parking Monitor
Hits the JustPark platform API directly to check July 19th availability.
No browser needed — fast and reliable.
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.request import urlopen, Request
from urllib.error import URLError

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

API_URL      = "https://platform.justpark.com/api/v1/smartpass/listings"
EVENT_ID     = "f293569b-b919-469b-b3ca-3ee4f950d16a"   # Match 104 — July 19th Final
CLIENT_ORG   = "f568ae9d-f263-4ef9-bf7e-56ef5fee8bbe"
AUTH_TOKEN   = "Basic N1kyWjRYOFc2VjNVMVQ5UzdSNVEzUDFOOEwwSzJKOUg2OjRSOEcySDZGM0o5SzBMMU43UDVRMlI4UzNVOVYwVzFY"
PAGE_URL     = "https://www.justpark.com/us/event-parking/fifa-world-cup-2026/new-york-new-jersey-stadium/"
STATE_FILE   = "state.json"

EMAIL_SENDER    = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD  = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT = os.environ["EMAIL_RECIPIENT"]
# Supports multiple recipients separated by commas
RECIPIENT_LIST  = [e.strip() for e in EMAIL_RECIPIENT.split(",") if e.strip()]

# ─────────────────────────────────────────────


def fetch_listings() -> dict:
    """Call the JustPark API and return the raw JSON response."""
    payload = json.dumps({
        "clientOrgKey": CLIENT_ORG,
        "events": [EVENT_ID],
        "thirdPartyLandmarks": []
    }).encode("utf-8")

    req = Request(
        API_URL,
        data=payload,
        headers={
            "Authorization":  AUTH_TOKEN,
            "Content-Type":   "application/json",
            "Accept":         "*/*",
            "Origin":         "https://eventpass.justpark.com",
            "Referer":        "https://eventpass.justpark.com/",
            "User-Agent":     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        },
        method="POST"
    )

    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_status(data: dict) -> dict:
    """Pull out the key availability fields from the API response."""
    listings = data if isinstance(data, list) else data.get("listings", data.get("data", []))

    status = {
        "checked_at": datetime.now().isoformat(),
        "listings":   []
    }

    for item in (listings if isinstance(listings, list) else []):
        lot    = item.get("lot", {})
        prices = item.get("prices", [])

        available_inventory = lot.get("availableInventory", None)
        is_available = (available_inventory is not None and available_inventory > 0)

        listing = {
            "name":                lot.get("name", item.get("identifier", "Unknown")),
            "available_inventory": available_inventory,
            "is_available":        is_available,
            "presell":             lot.get("presell", None),
            "prices": [
                {
                    "name":   p.get("name"),
                    "amount": p.get("amount"),   # in cents
                    "total":  p.get("total"),    # in cents inc. fees
                }
                for p in prices
            ],
        }
        status["listings"].append(listing)

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


def comparable(s: dict) -> dict:
    """Strip volatile fields for comparison — only care about availability changes."""
    if not s:
        return {}
    result = {k: v for k, v in s.items() if k not in ("checked_at",)}
    # Strip _raw from each listing to avoid noise
    if "listings" in result:
        result["listings"] = [
            {fk: fv for fk, fv in l.items() if fk != "_raw"}
            for l in result["listings"]
        ]
    return result


def send_email(old: dict, new: dict) -> None:
    subject = "🚨 FIFA World Cup Final Parking — July 19 Status Changed!"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    old_listings = {l["name"]: l for l in old.get("listings", [])}
    new_listings = {l["name"]: l for l in new.get("listings", [])}

    changes = []
    for name, new_l in new_listings.items():
        old_l = old_listings.get(name, {})
        diffs = []
        for field in ["available_inventory", "is_available", "presell", "prices"]:
            if old_l.get(field) != new_l.get(field):
                diffs.append(f"    {field}: {old_l.get(field)} → {new_l.get(field)}")
        if diffs:
            changes.append(f"  {name}:\n" + "\n".join(diffs))

    def fmt_listing(l):
        prices_str = ", ".join(f"{p['name']} ${p['total']/100:.2f}" for p in l.get('prices', []))
        avail = "✅ AVAILABLE" if l.get('is_available') else "❌ Not available"
        inv = l.get('available_inventory', 'unknown')
        return f"  {l['name']}\n    Status: {avail} (inventory: {inv})\n    Prices: {prices_str}"

    body = f"""
🚨 A change was detected on the JustPark July 19th FIFA World Cup Final parking!

Detected at: {timestamp}

WHAT CHANGED:
{chr(10).join(changes) if changes else '  General change detected — check the page.'}

CURRENT STATUS:
{chr(10).join(fmt_listing(l) for l in new.get('listings', []))}

➡ BUY NOW: {PAGE_URL}
"""

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = ", ".join(RECIPIENT_LIST)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, RECIPIENT_LIST, msg.as_string())

    print(f"  ✉  Alert sent to {RECIPIENT_LIST}")


def main() -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Querying JustPark API for July 19 listings...")

    try:
        data = fetch_listings()
    except URLError as e:
        print(f"  ✗  API request failed: {e}")
        return
    except Exception as e:
        print(f"  ✗  Unexpected error: {e}")
        return

    print(f"  Raw API response: {json.dumps(data)[:3000]}")
    if isinstance(data, list) and len(data) > 0:
        print(f"  All keys in first listing: {list(data[0].keys())}")

    current = extract_status(data)
    print(f"  Listings found: {len(current.get('listings', []))}")
    for l in current.get("listings", []):
        prices_str = ", ".join(f"{p['name']} ${p['total']/100:.2f}" for p in l.get('prices', []))
        print(f"    {l['name']}")
        print(f"      available_inventory: {l['available_inventory']}")
        print(f"      is_available:        {l['is_available']}")
        print(f"      presell:             {l['presell']}")
        print(f"      prices:              {prices_str}")

    state    = load_state()
    previous = state.get("status")

    if previous is None:
        print("  ✓  First run — baseline saved. No alert sent.")
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
