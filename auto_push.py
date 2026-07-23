"""
auto_push.py
监听 webapp/ 目录的文件变化,自动 git add + commit + push
依赖:pip install watchdog
用法:python auto_push.py [--once]
"""
import sys
import io
import subprocess
import time
from pathlib import Path
from datetime import datetime

# 强制 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("[ERR] 需要安装 watchdog: pip install watchdog")
    sys.exit(1)

REPO = Path(__file__).parent.resolve()
DEBOUNCE_SEC = 2.0  # 改动后 2 秒再触发,合并多次连续改动

class GitPusher(FileSystemEventHandler):
    def __init__(self):
        self.last_trigger = 0
        self.pending = False

    def on_any_event(self, event):
        if event.is_directory:
            return
        # 忽略 .git 内部变化
        if '.git' in event.src_path:
            return
        # 忽略常见无关文件
        if any(event.src_path.endswith(s) for s in ['.pyc', '.log', '.tmp', '~']):
            return
        rel = Path(event.src_path).relative_to(REPO)
        ts = time.time()
        if ts - self.last_trigger < DEBOUNCE_SEC:
            return
        self.last_trigger = ts
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 检测到变化: {event.event_type} {rel}")
        self.do_push()

    def do_push(self):
        try:
            # git add
            r = subprocess.run(["git", "add", "-A"], cwd=REPO, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[ERR] git add: {r.stderr}")
                return
            # 检查是否有 staged
            r = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=REPO, capture_output=True, text=True)
            if not r.stdout.strip():
                print("    (无 staged 内容,跳过)")
                return
            # git commit
            msg = f"auto: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            r = subprocess.run(["git", "commit", "-m", msg], cwd=REPO, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[ERR] git commit: {r.stderr}")
                return
            # git push
            r = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[ERR] git push: {r.stderr}")
                return
            print(f"    ✓ 已推送")
        except Exception as e:
            print(f"[ERR] {e}")

def main():
    if "--once" in sys.argv:
        # 单次模式:扫描+推一次就退出
        GitPusher().do_push()
        return

    print(f"")
    print(f"  监听目录: {REPO}")
    print(f"  防抖: {DEBOUNCE_SEC}s")
    print(f"  按 Ctrl+C 停止")
    print(f"")

    observer = Observer()
    handler = GitPusher()
    observer.schedule(handler, str(REPO), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[停止]")
        observer.join()

if __name__ == "__main__":
    main()
