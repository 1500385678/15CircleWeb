"""
_changelog_update.py
用 GitHub Contents API 把本地 CHANGELOG.md PUT 到 main 分支
(走 api.github.com:443 绕开 github.com:443 阻断)
"""
import base64
import json
import os
import urllib.request
from pathlib import Path

REPO = "1500385678/15CircleWeb"
FILE_PATH = "D:/Database/Database/Attack/15CircleDb/_scratch/15CircleWeb/CHANGELOG.md"
GITHUB_PATH = "CHANGELOG.md"
BRANCH = "main"
TOKEN = os.environ.get("GH_TOKEN")
if not TOKEN:
    raise SystemExit("GH_TOKEN env var not set")

# 1. 读本地 CHANGELOG.md
content_bytes = Path(FILE_PATH).read_bytes()
content_b64 = base64.b64encode(content_bytes).decode("ascii")
print(f"本地 CHANGELOG.md: {len(content_bytes)} bytes, sha1 = {hash(content_bytes)}")

# 2. 拿当前 GitHub 上的 blob SHA
url = f"https://api.github.com/repos/{REPO}/contents/{GITHUB_PATH}?ref={BRANCH}"
req = urllib.request.Request(url, headers={"User-Agent": "15CircleDb-agent", "Authorization": f"Bearer {TOKEN}"})
with urllib.request.urlopen(req, timeout=15) as r:
    current = json.loads(r.read())
current_sha = current["sha"]
print(f"GitHub 当前 sha: {current_sha}")

# 3. PUT 新内容
data = {
    "message": "docs: changelog v1.5.3",
    "branch": BRANCH,
    "sha": current_sha,
    "content": content_b64,
}
req = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/contents/{GITHUB_PATH}",
    data=json.dumps(data).encode("utf-8"),
    method="PUT",
    headers={
        "User-Agent": "15CircleDb-agent",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
    },
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read())
        print(f"OK -> commit {result['commit']['sha'][:8]}  {result['content']['html_url']}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"FAIL {e.code}: {body[:500]}")
