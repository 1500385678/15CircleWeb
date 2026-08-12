# 15CircleWeb

15 分钟生活圈配套数据库的可视化 Web 界面。  
配套数据库本体见 [15CircleDb](https://github.com/1500385678/15CircleDb) 仓库。

## 启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备数据库(从 15CircleDb 仓库获取)
#    将 15circledb.db 放在 webapp/ 同级或上级目录,app.py 自动探测:
#      - 优先尝试 webapp/../15circledb.db
#      - 其次尝试 webapp/../../15circledb.db
#    无需硬编码绝对路径,跨平台通用(Windows / macOS / Linux 都可)

# 3. 启动
python app.py
# → http://localhost:5000
```

### 生产部署

`app.py` 启动段已自动检测 `waitress`,优先用多线程生产服务器;缺包时降级到 Flask dev server。

```bash
# 推荐:装 waitress 后启动即生产模式
pip install waitress
python app.py  # 自动用 waitress · 4 threads

# 显式 waitress(完全控制参数)
waitress-serve --port=5000 --threads=4 app:app

# 或 gunicorn(需要 Linux,macOS 也可)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 自动推送到 GitHub

### 方式 A:文件监听(自动)
```bash
python auto_push.py
```
启动后监听本目录,任何文件改动后 2 秒自动 commit + push。

### 方式 B:手动单次推送
```powershell
.\_commit_push.ps1 "修复仪表盘布局"
# 或
_commit_push.bat "修复仪表盘布局"
```

推送使用 User-scope 环境变量 `$env:GH_TOKEN`(已设),无需每次粘贴。

> auto_push 启动时已加 preflight:若本仓库未配 `user.name` / `user.email`,自动回退为 `15CircleWeb Auto` / `auto@15circleweb.local`(只仓库 scope,不动 --global),无需手动 `git config` 即可 commit。

## 项目结构

```
15CircleWeb/
├── app.py                 # Flask 后端 (15 个 API)
├── templates\
│   └── index.html         # 单页应用 (HTML + 内联 JS)
├── static\
│   ├── src.css            # Tailwind 源 (本地编译)
│   ├── tailwind.config.js
│   ├── tailwind.css       # Tailwind 编译产物 (13.7KB)
│   └── chart.umd.min.js   # Chart.js 4.4.0 本地 (200KB)
├── auto_push.py           # 文件监听 → 自动推送
├── _commit_push.ps1       # PowerShell 手动推送
├── _commit_push.bat       # CMD 手动推送
├── requirements.txt       # 依赖
├── .gitignore
└── README.md
```

## API 端点(15 个)

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/stats` | GET | 数据库统计(10 张表 COUNT 合并为 1 SQL) |
| `/api/dashboard_summary` | GET | 仪表盘聚合端点(消除 N+1) |
| `/api/circles` | GET | 5 级生活圈 |
| `/api/circles/<code>/facilities` | GET | 单圈层配建清单(支持 ?priority=必配/宜配/参考) |
| `/api/circles/facilities/all` | GET | 全部圈层 × 全部优先级 一次拉取(径向图聚合) |
| `/api/calculate` | GET | 反推配建计算(根据人口/圈层类型) |
| `/api/cases` | GET | 案例列表(含 `facilities_count` / `projects_count`) |
| `/api/cases/<code>` | GET | 案例详情(含 `facilities` / `projects`) |
| `/api/cases/<code>/projects` | GET | 案例项目清单(按类目分组) |
| `/api/massing/cases/<code>` | GET | 案例体块推算(面积 / 配比 / 三维像素) |
| `/api/massing/circles/<code>` | GET | 圈层体块推算 |
| `/api/categories` | GET | 分类树 |
| `/api/facilities` | GET | 设施列表(68 个) |
| `/api/search` | GET | 关键词搜索(支持中英别名,LIKE 通配符已转义) |
| `/api/standards` | GET | 规范来源(10 份,url 走服务端 + 客户端双层 http(s) 协议白名单防 XSS) |

## 数据库要求

Web 应用的 `app.py` 默认从以下路径读取 SQLite:

```python
# app.py 自动探测(webapp/ 同级或上级目录任一)
_candidates = [BASE.parent / "15circledb.db", BASE.parent.parent / "15circledb.db"]
DB = next((p for p in _candidates if p.exists()), _candidates[0])
```

完整数据库建库流程见 [15CircleDb 仓库](https://github.com/1500385678/15CircleDb) 的 README。

## 视图

| 视图 | 功能 |
|---|---|
| 仪表盘 | 5 张统计卡 + 圈层设施柱状图 + 设施分类饼图 + 案例速览 + 圈层对照表(单屏显示) |
| 圈层配建 | 切换 5/10/15min 圈层,展示必配/宜配清单 |
| 配建计算器 | 输入人口 → 反推 5/10/15min 应配清单 + 总面积 |
| 案例对比 | 上海/苏州/新加坡案例卡片,支持国家过滤 |
| 设施库 | 左侧分类树 + 右侧 68 个设施清单 |
| 规范来源 | 10 份规范文件卡片 |
| 全局搜索 | 顶栏搜索框,跨中英别名搜索 |
