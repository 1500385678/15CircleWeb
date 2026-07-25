"""
_push_to_both.py
一次提交,推到 GitHub + Gitee(互不依赖,任一失败不影响另一个)
- push 前自动 fetch + rebase 整合(避免分叉)
- 任一边失败不影响另一边
用法:  python _push_to_both.py [commit_msg]
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent

def run(cmd, cwd=REPO):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def push_to(remote):
    """fetch + rebase + push,失败不算 fatal"""
    print(f"\n--- 推 {remote} ---")
    # 1. fetch
    rc, out, err = run(f"git fetch {remote} main")
    if rc != 0:
        print(f"  fetch FAIL: {err[:200]}")
        return False
    # 2. rebase 整合
    rc, out, err = run(f"git rebase {remote}/main")
    if rc != 0:
        # rebase 冲突,abort
        run("git rebase --abort")
        print(f"  rebase 冲突已 abort,跳过 {remote}")
        return False
    # 3. push
    rc, out, err = run(f"git push {remote} main")
    if rc == 0:
        print(f"  OK  {out.split(chr(10))[-1] if out else 'pushed'}")
        return True
    else:
        print(f"  push FAIL: {err[:300]}")
        return False

commit_msg = sys.argv[1] if len(sys.argv) > 1 else f"chore: update"

# 1. 检查状态
rc, out, _ = run("git status --short")
if not out:
    print("无变更,无需提交")
    sys.exit(0)
print(f"待提交变更:\n{out}")

# 2. add + commit
rc, out, err = run(f'git add -A && git -c user.name="15CircleDb agent" -c user.email="15circledb@local" commit -m "{commit_msg}"')
if rc != 0:
    print(f"commit 失败: {err}")
    sys.exit(1)
print(f"\n[commit] {out.split(chr(10))[-1]}")

# 3. 推两边(互不影响)
results = {}
for remote in ["origin", "gitee"]:
    results[remote] = push_to(remote)

# 4. 推 tags
print("\n--- 推 tags ---")
for remote in ["origin", "gitee"]:
    rc, _, err = run(f"git push {remote} --tags")
    if rc == 0:
        print(f"  {remote}: OK")
    else:
        print(f"  {remote}: FAIL {err[:200]}")

print(f"\n=== 完成 ===  GitHub: {'OK' if results.get('origin') else 'FAIL'}  Gitee: {'OK' if results.get('gitee') else 'FAIL'}")
