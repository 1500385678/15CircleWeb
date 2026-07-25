"""
_push_to_both.py
一次提交,推到 GitHub + Gitee(互不依赖,任一失败不影响另一个)
用法:  python _push_to_both.py [commit_msg]
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent

def run(cmd, cwd=REPO):
    """Run command, return (returncode, stdout, stderr)"""
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip(), r.stderr.strip()

commit_msg = sys.argv[1] if len(sys.argv) > 1 else f"chore: update {Path(__file__).stat().st_mtime}"

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

# 3. 推 GitHub
print("\n--- 推 GitHub (origin) ---")
rc, out, err = run("git push origin main")
if rc == 0:
    print(f"OK  {out.split(chr(10))[-1] if out else 'pushed'}")
else:
    print(f"FAIL  {err[:300]}")
    print("  (但仍会推 Gitee)")

# 4. 推 Gitee
print("\n--- 推 Gitee (gitee remote) ---")
rc, out, err = run("git push gitee main")
if rc == 0:
    print(f"OK  {out.split(chr(10))[-1] if out else 'pushed'}")
else:
    print(f"FAIL  {err[:300]}")
    print("  (但 GitHub 推成功不算失败)")

# 5. 推 tags
print("\n--- 推 tags 到两边 ---")
for remote in ["origin", "gitee"]:
    print(f"  -> {remote}")
    rc, _, err = run(f"git push {remote} --tags")
    if rc == 0:
        print(f"     OK")
    else:
        print(f"     FAIL: {err[:200]}")

print("\n=== 完成 ===")
