from flask import Flask, jsonify
from flask_cors import CORS
import requests, os

app = Flask(__name__)
CORS(app)  # Allow portfolio frontend to call this

GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")
GITHUB_USERNAME = "dhanushin2k23"
LEETCODE_USERNAME = "dhanushin2k23"

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
            "Referer": "https://leetcode.com"
        },
        timeout=10
    ).json()

    user = resp["data"]["matchedUser"]
    stats = {s["difficulty"]: s["count"] for s in user["submitStats"]["acSubmissionNum"]}

    import json
    # submissionCalendar: {"timestamp": count, ...}
    raw_cal = json.loads(user["userCalendar"]["submissionCalendar"])
    # Convert unix timestamps to date strings
    from datetime import datetime, timezone
    calendar = [
        {"date": datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d"),
         "count": cnt}
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


if __name__ == "__main__":
    app.run(debug=True, port=5001)
