"""
_gitee_verify.py
验证 Gitee 仓库内容
"""
import json
import os
import urllib.request

GITEE_USER  = "architectzy"
GITEE_TOKEN = "5ed52babcbfa332404a11863bc065b00"
REPO_NAME   = "15CircleWeb"

API = "https://gitee.com/api/v5"

# 1. 仓库信息
print("=== 仓库信息 ===")
req = urllib.request.Request(
    f"{API}/repos/{GITEE_USER}/{REPO_NAME}",
    headers={"Authorization": f"token {GITEE_TOKEN}"},
)
with urllib.request.urlopen(req, timeout=15) as r:
    repo = json.loads(r.read())
    print(f"  full_name: {repo.get('full_name')}")
    print(f"  html_url:  {repo.get('html_url')}")
    print(f"  default_branch: {repo.get('default_branch')}")
    print(f"  size:      {repo.get('size')} KB")
    print(f"  stars:     {repo.get('stars_count')}")
    print(f"  forks:     {repo.get('forks_count')}")

# 2. 最新 release
print("\n=== 最新 release ===")
req = urllib.request.Request(
    f"{API}/repos/{GITEE_USER}/{REPO_NAME}/releases/latest",
    headers={"Authorization": f"token {GITEE_TOKEN}"},
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        rel = json.loads(r.read())
        print(f"  tag:       {rel.get('tag_name')}")
        print(f"  name:      {rel.get('name')}")
        print(f"  url:       {rel.get('html_url')}")
except Exception as e:
    print(f"  无 release / 错误: {e}")

# 3. tags 数量
print("\n=== Tags ===")
req = urllib.request.Request(
    f"{API}/repos/{GITEE_USER}/{REPO_NAME}/tags",
    headers={"Authorization": f"token {GITEE_TOKEN}"},
)
with urllib.request.urlopen(req, timeout=15) as r:
    tags = json.loads(r.read())
    print(f"  count: {len(tags)}")
    for t in tags:
        print(f"  {t.get('name')}")
