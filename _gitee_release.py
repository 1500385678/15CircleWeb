"""
_gitee_release.py
为 Gitee 仓库创建 v1.5.3 release
"""
import json
import os
import urllib.request
import urllib.error

GITEE_USER  = "architectzy"
GITEE_TOKEN = "5ed52babcbfa332404a11863bc065b00"
REPO_NAME   = "15CircleWeb"
TAG_NAME    = "v1.5.3"
RELEASE_NAME = "v1.5.3 — Bugfix DB 路径"
RELEASE_BODY = """## 修复
- `app.py` 第 14-16 行: DB 路径从 `BASE.parent / "15circledb.db"` 改为
  优先匹配 `BASE.parent`,失败回退 `BASE.parent.parent`,适应两种部署:
  - 仓库根目录跑 → `webapp/app.py` + `15circledb.db` 同级 ✓
  - 嵌套目录跑 → `_scratch/webapp/app.py` + `_scratch/../15circledb.db` ✓

## 触发场景
之前 `/api/stats`、`/api/cases` 等所有 API 返回 500:
```
sqlite3.OperationalError: no such table: standards
```
但首页 `/` 能返回(因为只读 templates)。本地调试入口 → 修复后 API 全部 200。

## 版本
- App: v1.5.2 → v1.5.3
- DB: v1.0.0(无变化)
"""

API = "https://gitee.com/api/v5"
body = {
    "tag_name": TAG_NAME,
    "name": RELEASE_NAME,
    "body": RELEASE_BODY,
    "target_commitish": "main",
    "prerelease": False,
}

req = urllib.request.Request(
    f"{API}/repos/{GITEE_USER}/{REPO_NAME}/releases",
    data=json.dumps(body).encode("utf-8"),
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"token {GITEE_TOKEN}",
        "User-Agent": "15CircleDb-agent",
    },
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        result = json.loads(r.read())
        print(f"OK release created:")
        print(f"  tag:   {result.get('tag_name')}")
        print(f"  name:  {result.get('name')}")
        print(f"  url:   {result.get('html_url')}")
except urllib.error.HTTPError as e:
    body_text = e.read().decode("utf-8", errors="replace")
    print(f"FAIL {e.code}: {body_text[:500]}")
