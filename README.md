# 15CircleWeb

15 分钟生活圈配套数据库的可视化 Web 界面。  
配套数据库本体见 [15CircleDb](https://github.com/1500385678/15CircleDb) 仓库。

## 启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备数据库(从 15CircleDb 仓库获取,放在上级目录)
#    路径要求:D:\Database\Database\Attack\15CircleDb\15circledb.db

# 3. 启动
python app.py
# → http://localhost:5000
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

## 项目结构

```
15CircleWeb/
├── app.py                 # Flask 后端 (10 个 API)
├── templates\
│   └── index.html         # 单页应用 (HTML + 内联 JS)
├── auto_push.py           # 文件监听 → 自动推送
├── _commit_push.ps1       # PowerShell 手动推送
├── _commit_push.bat       # CMD 手动推送
├── requirements.txt       # 依赖
├── .gitignore
└── README.md
```

## API 端点(10 个)

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/stats` | GET | 数据库统计 |
| `/api/circles` | GET | 5 级生活圈 |
| `/api/circles/<code>/facilities` | GET | 圈层配建清单 |
| `/api/calculate` | GET | 反推配建计算 |
| `/api/cases` | GET | 案例列表 |
| `/api/cases/<code>` | GET | 案例详情 |
| `/api/categories` | GET | 分类树 |
| `/api/facilities` | GET | 设施列表 |
| `/api/search` | GET | 关键词搜索 |
| `/api/standards` | GET | 规范来源 |

## 数据库要求

Web 应用的 `app.py` 默认从以下路径读取 SQLite:

```python
DB = BASE.parent / "15circledb.db"   # 上级目录
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
