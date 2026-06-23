from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, os, json, re
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)  # Allow portfolio frontend to call this

GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")
GITHUB_USERNAME = "dhanushin2k23"
LEETCODE_USERNAME = "dhanushin2k23"
CONTACT_EMAIL   = os.environ.get("CONTACT_EMAIL", "dhanushin2k23@gmail.com")
WEB3FORMS_KEY   = os.environ.get("WEB3FORMS_ACCESS_KEY")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# ── GitHub ──────────────────────────────────────────────
@app.route("/api/github")
def github():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    # Basic user stats
    user = requests.get(
        f"https://api.github.com/users/{GITHUB_USERNAME}",
        headers=headers, timeout=10
    ).json()

    # Contribution graph via GraphQL
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    gql = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": GITHUB_USERNAME}},
        headers=headers, timeout=10
    ).json()

    calendar = gql["data"]["user"]["contributionsCollection"]["contributionCalendar"]

    # Flatten weeks → days array
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append({
                "date":  day["date"],
                "count": day["contributionCount"]
            })

    return jsonify({
        "repos":         user.get("public_repos", 0),
        "followers":     user.get("followers", 0),
        "total_contributions": calendar["totalContributions"],
        "days":          days   # [{date, count}, ...]
    })


# ── LeetCode ────────────────────────────────────────────
@app.route("/api/leetcode")
def leetcode():
    # LeetCode has no official API — using their public GraphQL endpoint
    query = """
    query($username: String!) {
      matchedUser(username: $username) {
        submitStats {
          acSubmissionNum {
            difficulty
            count
          }
        }
        userCalendar {
          submissionCalendar
        }
        profile {
          ranking
        }
      }
    }
    """
    resp = requests.post(
        "https://leetcode.com/graphql",
        json={"query": query, "variables": {"username": LEETCODE_USERNAME}},
        headers={
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "Origin": "https://leetcode.com",
        },
        timeout=15
    ).json()

    if resp.get("errors") or not resp.get("data", {}).get("matchedUser"):
        return jsonify({"error": "LeetCode user not found"}), 404

    user = resp["data"]["matchedUser"]
    stats = {s["difficulty"]: s["count"] for s in user["submitStats"]["acSubmissionNum"]}

    raw_cal = user["userCalendar"]["submissionCalendar"] or "{}"
    if isinstance(raw_cal, str):
        raw_cal = json.loads(raw_cal)

    calendar = [
        {
            "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d"),
            "count": int(cnt),
        }
        for ts, cnt in raw_cal.items()
    ]

    return jsonify({
        "total":  stats.get("All", 0),
        "easy":   stats.get("Easy", 0),
        "medium": stats.get("Medium", 0),
        "hard":   stats.get("Hard", 0),
        "ranking": user["profile"]["ranking"],
        "days":   calendar  # [{date, count}, ...]
    })


# ── Contact form ────────────────────────────────────────
@app.route("/api/contact", methods=["POST"])
def contact():
    if not WEB3FORMS_KEY:
        return jsonify({"error": "Contact form is not configured on the server"}), 503

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:200]
    email = (data.get("email") or "").strip()[:254]
    message = (data.get("message") or "").strip()[:5000]

    if not name or not email or not message:
        return jsonify({"error": "All fields are required"}), 400

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Invalid email address"}), 400

    try:
        resp = requests.post(
            "https://api.web3forms.com/submit",
            json={
                "access_key": WEB3FORMS_KEY,
                "name": name,
                "email": email,
                "message": message,
                "subject": f"Portfolio contact from {name}",
                "replyto": email,
                "from_name": "DHANUSH Portfolio",
            },
            timeout=15,
        )
        result = resp.json()
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Failed to send message"}), 502

    if result.get("success"):
        return jsonify({"ok": True})

    return jsonify({"error": result.get("message", "Failed to send message")}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5001)
