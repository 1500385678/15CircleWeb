"""
_gitee_setup.py
在 Gitee 上创建 15CircleWeb 仓库(如果还没有),并把本地 main 推上去
"""
import json
import os
import urllib.request
import urllib.error

GITEE_USER  = "architectzy"
GITEE_TOKEN = os.environ.get("GITEE_TOKEN") or "5ed52babcbfa332404a11863bc065b00"
REPO_NAME   = "15CircleWeb"
REPO_DESC   = "15 分钟生活圈配套数据库 - Web 可视化 (Flask + SQLite)"

API = "https://gitee.com/api/v5"

def call(method, path, body=None, auth=True):
    url = f"{API}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "15CircleDb-agent"}
    if auth:
        headers["Authorization"] = f"token {GITEE_TOKEN}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return e.code, body_text

# 1. 验证 token + 拿 user info
print("=== 1. 验证 Gitee token ===")
status, me = call("GET", "/user")
if status != 200:
    print(f"FAIL {status}: {me}")
    raise SystemExit(1)
print(f"OK  user: {me.get('login')}  id={me.get('id')}  name={me.get('name')}")

# 2. 看仓库是否存在
print(f"\n=== 2. 检查仓库 {GITEE_USER}/{REPO_NAME} ===")
status, existing = call("GET", f"/repos/{GITEE_USER}/{REPO_NAME}", auth=False)
if status == 200:
    print(f"EXISTS  -> 跳过创建,直接 push")
    print(f"  url: {existing.get('html_url')}")
    print(f"  ssh: {existing.get('ssh_url')}")
    print(f"  https: {existing.get('git_url')}")
elif status == 404:
    print("NOT FOUND  ->  创建中...")
    body = {
        "name": REPO_NAME,
        "description": REPO_DESC,
        "private": False,
        "has_issues": True,
        "has_wiki": False,
        "auto_init": False,  # 不自动 init,我们要从 GitHub 推
    }
    status, created = call("POST", "/user/repos", body=body)
    if status == 201:
        print(f"OK created")
        print(f"  url: {created.get('html_url')}")
        print(f"  ssh: {created.get('ssh_url')}")
        print(f"  https: {created.get('git_url')}")
    else:
        print(f"FAIL {status}: {created}")
        raise SystemExit(1)
else:
    print(f"UNEXPECTED {status}: {existing}")
    raise SystemExit(1)

# 3. 准备 push 命令
print(f"\n=== 3. 接下来手动 push(由调用方执行 git push gitee main) ===")
print("gitee remote URL:")
print(f"  https://{GITEE_USER}:{GITEE_TOKEN}@gitee.com/{GITEE_USER}/{REPO_NAME}.git")
