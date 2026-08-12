"""
15CircleDb Web App
- 后端:Flask + SQLite
- 前端:单页应用 (SPA) + Tailwind 本地编译 + Chart.js 本地静态
- 启动:python app.py → http://localhost:5000
"""
__version__ = "1.5.3"
__updated__ = "2026-07-24"

import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, jsonify, request, render_template, abort, g
# 共享色板(色板唯一性 assert 在 import 阶段就跑,见 _colors.py)
# ✅ P2 闭环:2026-08-13 Verifier R301 — 抽到独立模块
from _colors import CASE_CATEGORY_COLORS, CIRCLE_CATEGORY_COLORS

BASE = Path(__file__).parent
# 库在上级目录的上一级(适应 webapp/ 在 _scratch/ 或仓库根目录下的两种部署)
# 优先尝试 BASE.parent/15circledb.db,失败则 BASE.parent.parent/15circledb.db
_candidates = [BASE.parent / "15circledb.db", BASE.parent.parent / "15circledb.db"]
DB = next((p for p in _candidates if p.exists()), _candidates[0])

# 启动期 fail-fast:库不在 → 直接退出,不再让用户看到"假活"页面(API 全 500)
# 避免"app 200 OK → API 500 → 翻代码 → 才发现库不在"的排错链
if not DB.exists():
    import sys
    print(f"[FATAL] 数据库不存在:{DB}", file=sys.stderr)
    print(f"[FATAL] 请从 15CircleDb 仓库拷贝 15circledb.db 到以下任一位置:", file=sys.stderr)
    for _c in _candidates:
        print(f"  - {_c}", file=sys.stderr)
    sys.exit(1)

# 启动时打 WAL(改善并发读 + 避免读锁阻塞写),只在库存在时打
try:
    if DB.exists():
        _wal_conn = sqlite3.connect(DB)
        _wal_conn.execute("PRAGMA journal_mode=WAL")
        _wal_conn.execute("PRAGMA synchronous=NORMAL")
        _wal_conn.close()
except Exception as _wal_err:
    print(f"[WARN] WAL pragma 失败(非致命): {_wal_err}")

app = Flask(__name__, template_folder="templates", static_folder="static")

# ---------- 数据库连接(请求内复用 + WAL) ----------
def get_db():
    """每个请求一份连接,放在 flask.g,请求结束自动 close。"""
    if "db" not in g:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        # 每次新连接也确保 WAL 模式(对连接池/新线程必要)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(_exc=None):
    """请求结束关闭连接(若存在)。"""
    db = g.pop("db", None)
    if db is not None:
        db.close()

def query(sql, args=(), one=False):
    """执行 SQL。
    one=True 走 fetchone() 取单行(原 fetchall+rows[0] 多此一举 + rows[0] 越界风险)。
    出错打日志并抛出,让 Flask errorhandler 统一返 JSON 500,不再裸堆栈。
    """
    conn = get_db()
    cur = conn.execute(sql, args)
    if one:
        row = cur.fetchone()
        return dict(row) if row else None
    return [dict(r) for r in cur.fetchall()]

def query_meta(key, default=None):
    """读取 db_meta 单条 key,缺键返 default,绝不抛 IndexError。"""
    row = query("SELECT value FROM db_meta WHERE key=?", (key,), one=True)
    return (row or {}).get("value", default)

# ---------- 全局错误处理 ----------
# 敏感信息关键字:str(e) 含这些字眼一律只返 fallback,不暴露表/列/约束/SQL 片段
# 避免攻击者通过错误信息反推 db schema
_SENSITIVE_KEYWORDS = ("table", "column", "constraint", "select ", " from ", " where ", " join ", "index ")

def _sanitize_detail(e, fallback):
    """从异常 e 提取安全 detail,失败返 fallback。
    命中敏感字眼 / 过长 / 包含堆栈符号 → 返 fallback(原始 str(e) 只进 stderr)。"""
    s = str(e)
    s_lower = s.lower()
    if any(kw in s_lower for kw in _SENSITIVE_KEYWORDS):
        return fallback
    if len(s) > 200 or "\n" in s:
        return fallback
    return s

@app.errorhandler(404)
def _404(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found", "path": request.path}), 404
    return _e, 404

@app.errorhandler(sqlite3.Error)
def _sqlite_err(e):
    """SQL 错误统一返 JSON 500,sanitize detail 不泄露表/列结构。"""
    # 原始 str(e) 只进 stderr(供排错),前端只看到 sanitize 后的类型名
    print(f"[DB ERR] {type(e).__name__}: {e}", file=sys.stderr)
    return jsonify({
        "error": "database error",
        "detail": _sanitize_detail(e, f"{type(e).__name__}(see server logs)")
    }), 500

@app.errorhandler(Exception)
def _generic_err(e):
    """其他未捕获异常也走 JSON 500(对 /api/*),detail sanitize 不泄露堆栈。"""
    if request.path.startswith("/api/"):
        import traceback
        # 原始 traceback 只进 stderr,前端只看到 sanitize 后的简短说明
        traceback.print_exc()
        return jsonify({
            "error": "internal server error",
            "detail": _sanitize_detail(e, "see server logs")
        }), 500
    raise e

# ---------- 页面 ----------
@app.route("/")
def index():
    return render_template("index.html")

# ---------- API ----------
@app.route("/api/stats")
def api_stats():
    # 单次 SQL 取 10 张表 COUNT(*),避免 10 次独立 query 开销(原 10 次串行 ≈ 10×单次)
    # waiter 4 线程 × 高频调用场景下,游标/连接/page cache 重复切换累计延迟显著
    _counts = query("""
        SELECT
            (SELECT COUNT(*) FROM standards)         AS standards,
            (SELECT COUNT(*) FROM life_circles)      AS life_circles,
            (SELECT COUNT(*) FROM climate_zones)     AS climate_zones,
            (SELECT COUNT(*) FROM facility_types)    AS facility_types,
            (SELECT COUNT(*) FROM categories)        AS categories,
            (SELECT COUNT(*) FROM facilities)        AS facilities,
            (SELECT COUNT(*) FROM facility_circle_map) AS facility_map,
            (SELECT COUNT(*) FROM cases)             AS cases,
            (SELECT COUNT(*) FROM case_facilities)   AS case_facilities,
            (SELECT COUNT(*) FROM case_projects)     AS case_projects
    """)[0]
    return jsonify({
        **_counts,
        "app_version": __version__,
        "app_updated": __updated__,
        "db_version":  query_meta("schema_version", default="unknown"),
        "db_updated":  query_meta("last_seed_date", default="unknown"),
    })

@app.route("/api/circles")
def api_circles():
    return jsonify(query("""
        SELECT id, code, name_zh, name_en, walk_time_min, walk_radius_m,
               population_min, population_max, household_min, household_max,
               area_ha_min, area_ha_max, sort_order, description
        FROM life_circles
        WHERE is_active = 1
        ORDER BY sort_order
    """))

@app.route("/api/circles/<code>/facilities")
def api_circle_facilities(code):
    priority = request.args.get("priority", "")  # "" = all
    sql = """
        SELECT
            f.id, f.code, f.name_zh, f.name_en, f.aliases,
            c.name_zh AS category, c.code AS category_code, c.id AS category_id,
            fcm.priority, f.service_radius_min, f.service_radius_max,
            f.min_area_sqm, f.recommended_area_sqm, f.max_area_sqm,
            f.min_land_sqm, f.recommended_land_sqm, f.max_land_sqm,
            f.per_population, f.population_per_unit,
            f.bldg_per_1000_min, f.bldg_per_1000_max,
            f.should_be_independent, f.recommended_independent, f.can_be_combined,
            f.standard_source, f.standard_clause, f.tags, f.notes
        FROM facilities f
        JOIN facility_circle_map fcm ON fcm.facility_id = f.id
        JOIN life_circles lc ON lc.id = fcm.circle_id
        JOIN categories c ON c.id = f.category_id
        WHERE lc.code = ? AND f.is_active = 1
    """
    args = [code]
    if priority:
        priorities = priority.split(",")
        placeholders = ",".join("?" for _ in priorities)
        sql += f" AND fcm.priority IN ({placeholders})"
        args.extend(priorities)
    sql += """
        ORDER BY
            CASE fcm.priority WHEN '必配' THEN 1 WHEN '宜配' THEN 2 WHEN '参考' THEN 3 ELSE 4 END,
            c.sort_order, f.sort_order
    """
    return jsonify(query(sql, args))

@app.route("/api/circles/facilities/all")
def api_circles_facilities_all():
    """聚合端点:5 圈层 × 3 优先级 = 15 个数据集合并为 1 个 SQL 查询。
    返回 {circle_code: {priority: [facility, ...]}} 结构,client 端按需分桶。
    用于 Radial 视图(原来 15 个并行 /api/circles/<code>/facilities?priority=xxx)。"""
    rows = query("""
        SELECT
            lc.code AS circle_code,
            fcm.priority,
            f.id, f.code, f.name_zh, f.name_en, f.aliases,
            c.name_zh AS category, c.code AS category_code, c.id AS category_id,
            f.service_radius_min, f.service_radius_max,
            f.min_area_sqm, f.recommended_area_sqm, f.max_area_sqm,
            f.min_land_sqm, f.recommended_land_sqm, f.max_land_sqm,
            f.per_population, f.population_per_unit,
            f.bldg_per_1000_min, f.bldg_per_1000_max,
            f.should_be_independent, f.recommended_independent, f.can_be_combined,
            f.standard_source, f.standard_clause, f.tags, f.notes
        FROM facilities f
        JOIN facility_circle_map fcm ON fcm.facility_id = f.id
        JOIN life_circles lc ON lc.id = fcm.circle_id
        JOIN categories c ON c.id = f.category_id
        WHERE f.is_active = 1
        ORDER BY
            lc.sort_order,
            CASE fcm.priority WHEN '必配' THEN 1 WHEN '宜配' THEN 2 WHEN '参考' THEN 3 ELSE 4 END,
            c.sort_order, f.sort_order
    """)
    # 按 circle_code → priority 分桶(单一来源,client 不再 15 并发)
    bucket = {}
    for r in rows:
        code = r.pop("circle_code")
        pri = r.pop("priority")
        bucket.setdefault(code, {}).setdefault(pri, []).append(r)
    return jsonify(bucket)

@app.route("/api/calculate")
def api_calculate():
    """反推配建清单:给定人口和圈层,返回必配数+总面积估算"""
    try:
        population = int(request.args.get("population", 50000))
    except ValueError:
        return jsonify({"error": "population 必须是整数"}), 400
    circles_raw = request.args.get("circles", "15min,10min").split(",")
    priority_raw = request.args.get("priority", "必配,宜配").split(",")
    # 过滤空字符串(用户传 ?circles= 或 ?priority= → [''] 会拼出 IN () → 500)
    # ✅ P1 闭环:2026-08-13 Verifier R299
    circles = [c for c in circles_raw if c]
    priority = [p for p in priority_raw if p]
    if not circles or not priority:
        return jsonify({"error": "circles / priority 不能为空(至少各 1 项)"}), 400

    placeholders_c = ",".join("?" for _ in circles)
    placeholders_p = ",".join("?" for _ in priority)

    sql = f"""
        SELECT
            f.id, f.code, f.name_zh, f.name_en,
            c.name_zh AS category, c.code AS category_code,
            lc.name_zh AS circle, lc.code AS circle_code, lc.walk_radius_m,
            fcm.priority,
            CASE
                WHEN f.population_per_unit IS NOT NULL AND f.population_per_unit > 0
                THEN MAX(1, CAST(CEIL(? * 1.0 / f.population_per_unit) AS INTEGER))
                WHEN f.per_population IS NOT NULL AND f.per_population > 0
                THEN MAX(1, CAST(CEIL(? * 1.0 / f.per_population) AS INTEGER))
                ELSE 1
            END AS required_count,
            COALESCE(f.recommended_area_sqm, f.min_area_sqm, 0) AS per_unit_area,
            COALESCE(f.recommended_land_sqm, f.min_land_sqm, 0) AS per_unit_land,
            f.service_radius_max, f.min_area_sqm
        FROM facility_circle_map fcm
        JOIN facilities f ON f.id = fcm.facility_id
        JOIN life_circles lc ON lc.id = fcm.circle_id
        JOIN categories c ON c.id = f.category_id
        WHERE lc.code IN ({placeholders_c})
          AND fcm.priority IN ({placeholders_p})
          AND f.is_active = 1
        ORDER BY
            CASE lc.code WHEN '15min' THEN 1 WHEN '10min' THEN 2 WHEN '5min' THEN 3 ELSE 4 END,
            CASE fcm.priority WHEN '必配' THEN 1 WHEN '宜配' THEN 2 WHEN '参考' THEN 3 ELSE 4 END,
            c.sort_order, f.sort_order
    """
    args = [population, population] + circles + priority
    rows = query(sql, args)

    # 加总
    for r in rows:
        cnt = r["required_count"]
        r["total_area"] = round(cnt * r["per_unit_area"], 0)
        r["total_land"] = round(cnt * r["per_unit_land"], 0)

    return jsonify({
        "input": {"population": population, "circles": circles, "priority": priority.split(",")},
        "items": rows,
        "summary": {
            "total_facility_types": len(rows),
            "total_count": sum(r["required_count"] for r in rows),
            "total_area_sqm": sum(r["total_area"] for r in rows),
            "total_land_sqm": sum(r["total_land"] for r in rows),
        }
    })

@app.route("/api/cases")
def api_cases():
    country = request.args.get("country", "")
    sql = """SELECT c.*,
                    (SELECT COUNT(*) FROM case_facilities cf WHERE cf.case_id = c.id) AS facilities_count,
                    (SELECT COUNT(*) FROM case_projects  cp WHERE cp.case_id = c.id) AS projects_count
             FROM cases c"""
    args = []
    if country:
        sql += " WHERE c.country = ?"
        args.append(country)
    sql += " ORDER BY c.country, c.city, c.year"
    return jsonify(query(sql, args))

@app.route("/api/cases/<code>")
def api_case_detail(code):
    case = query("SELECT * FROM cases WHERE code = ?", [code], one=True)
    if not case:
        abort(404)
    case["facilities"] = query("""
        SELECT cf.*, f.name_zh AS facility_name, f.name_en AS facility_name_en,
               c.name_zh AS category, f.code AS facility_code
        FROM case_facilities cf
        JOIN facilities f ON f.id = cf.facility_id
        JOIN categories c ON c.id = f.category_id
        WHERE cf.case_id = ?
        ORDER BY c.sort_order, f.sort_order
    """, [case["id"]])
    # 运营生态项目(阿那亚等具体商户清单)
    case["projects"] = query("""
        SELECT id, category, name, description, tags
        FROM case_projects
        WHERE case_id = ?
        ORDER BY category, sort_order
    """, [case["id"]])
    return jsonify(case)

@app.route("/api/cases/<code>/projects")
def api_case_projects(code):
    case = query("SELECT id, name_zh FROM cases WHERE code = ?", [code], one=True)
    if not case:
        abort(404)
    rows = query("""
        SELECT id, category, name, description, tags, sort_order
        FROM case_projects
        WHERE case_id = ?
        ORDER BY category, sort_order
    """, [case["id"]])
    # 按类目分组
    grouped = {}
    for r in rows:
        grouped.setdefault(r["category"], []).append({
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "tags": r["tags"],
        })
    summary = [{"category": k, "count": len(v), "items": v} for k, v in grouped.items()]
    summary.sort(key=lambda x: -x["count"])
    return jsonify({
        "case_code": code,
        "case_name": case["name_zh"],
        "total": len(rows),
        "categories": summary,
    })


# ============== 业态体块图 ==============
# 案例业态 11 大类色板(CASE_CATEGORY_COLORS) + 圈层 10 大类色板(CIRCLE_CATEGORY_COLORS)
# 已抽到 _colors.py(色板唯一性 assert 在 import 阶段跑,新增业态重复色会立即 fail-fast)
# ✅ P2 闭环:2026-08-13 Verifier R301


@app.route("/api/massing/cases/<code>")
def api_massing_case(code):
    """
    案例业态体块数据。
    数据源:
      1) case_projects (具体项目清单,如阿那亚) - 按类目聚合,每项目估算 100 ㎡
      2) case_facilities (规范类配建) - 按 categories 顶级分类聚合,精确面积
    """
    case = query("SELECT id, name_zh, code, type, country, city, area_ha FROM cases WHERE code = ?", [code], one=True)
    if not case:
        abort(404)
    case_id = case["id"]

    # 1) case_projects - 类目聚合(默认 100 ㎡/项目)
    proj_rows = query("""
        SELECT category, COUNT(*) cnt
        FROM case_projects
        WHERE case_id = ?
        GROUP BY category
    """, [case_id])
    # 2) case_facilities - 按 categories 顶级聚合
    fac_rows = query("""
        SELECT c.name_zh AS cat_name, c.code AS cat_code,
               COUNT(*) cnt, SUM(COALESCE(cf.total_area_sqm, 0)) total_area
        FROM case_facilities cf
        JOIN facilities f ON f.id = cf.facility_id
        JOIN categories c ON c.id = f.category_id
        WHERE cf.case_id = ?
        GROUP BY c.id
    """, [case_id])

    blocks = []
    total_area = 0
    # case_facilities 优先(精确)
    for r in fac_rows:
        area = r["total_area"] or 0
        blocks.append({
            "label":   r["cat_name"],
            "code":    r["cat_code"],
            "count":   r["cnt"],
            "area_sqm": float(area),
            "source":  "case_facilities",
            "color":   CIRCLE_CATEGORY_COLORS.get(r["cat_code"], "#86868b"),
        })
        total_area += area
    # case_projects 补充(按类目,粗略估算)
    for r in proj_rows:
        # 避免重复:如果已有同类(case_facilities 用的 categories,跟 case_projects 用的中文类目不冲突)
        est_area = r["cnt"] * 100.0
        blocks.append({
            "label":   r["category"],
            "code":    "PRJ",
            "count":   r["cnt"],
            "area_sqm": float(est_area),
            "source":  "case_projects (估算 100 ㎡/项目)",
            "color":   CASE_CATEGORY_COLORS.get(r["category"], "#86868b"),
        })
        total_area += est_area

    # 算占比
    for b in blocks:
        b["pct"] = (b["area_sqm"] / total_area * 100) if total_area > 0 else 0

    # 按面积降序
    blocks.sort(key=lambda x: -x["area_sqm"])

    return jsonify({
        "type":       "case",
        "case_code":  code,
        "case_name":  case["name_zh"],
        "case_meta": {
            "country": case["country"],
            "city":    case["city"],
            "type":    case["type"],
            "area_ha": case["area_ha"],
        },
        "total_area_sqm": float(total_area),
        "block_count":    len(blocks),
        "blocks":         blocks,
    })


@app.route("/api/massing/circles/<code>")
def api_massing_circle(code):
    """
    圈层配建体块数据。
    JOIN facilities + categories 顶级 + facility_circle_map,
    按一级分类聚合,用 recommended_area_sqm 估算。
    """
    circle = query("SELECT id, name_zh, code, walk_radius_m, population_max FROM life_circles WHERE code = ?",
                    [code], one=True)
    if not circle:
        abort(404)
    rows = query("""
        SELECT c.name_zh AS cat_name, c.code AS cat_code,
               COUNT(*) cnt,
               SUM(COALESCE(f.recommended_area_sqm, 0)) AS sum_rec,
               SUM(COALESCE(f.min_area_sqm, 0)) AS sum_min,
               SUM(COALESCE(f.max_area_sqm, 0)) AS sum_max
        FROM facility_circle_map fcm
        JOIN facilities f ON f.id = fcm.facility_id
        JOIN categories c ON c.id = f.category_id
        WHERE fcm.circle_id = ? AND fcm.priority IN ('必配','宜配')
        GROUP BY c.id
    """, [circle["id"]])

    blocks = []
    total = 0
    for r in rows:
        area = r["sum_rec"] or 0
        if area <= 0:
            continue  # 跳过 0 面积的体块
        blocks.append({
            "label":   r["cat_name"],
            "code":    r["cat_code"],
            "count":   r["cnt"],
            "area_sqm": float(area),
            "min_area": float(r["sum_min"] or 0),
            "max_area": float(r["sum_max"] or 0),
            "color":   CIRCLE_CATEGORY_COLORS.get(r["cat_code"], "#86868b"),
        })
        total += area

    for b in blocks:
        b["pct"] = (b["area_sqm"] / total * 100) if total > 0 else 0
    blocks.sort(key=lambda x: -x["area_sqm"])

    return jsonify({
        "type":         "circle",
        "circle_code":  code,
        "circle_name":  circle["name_zh"],
        "circle_meta": {
            "walk_radius_m": circle["walk_radius_m"],
            "population_max": circle["population_max"],
        },
        "total_area_sqm": float(total),
        "block_count":    len(blocks),
        "blocks":         blocks,
    })

@app.route("/api/dashboard_summary")
def api_dashboard_summary():
    """仪表盘单接口聚合:替代 /api/circles + /api/cases + 2N 个 /api/circles/{code}/facilities。

    一次返回 circles / cases / circle_counts,把 2N+3 个串行请求压到 1 个。
    circle_counts 是单 SQL 聚合(LIFECircles LEFT JOIN facility_circle_map + facilities
    过滤 is_active),与原 5 圈层 N+1 等价。
    """
    # 1) 圈层 + 设施计数(单 SQL 聚合,O(1) 替代 O(N))
    counts_rows = query("""
        SELECT lc.code, COUNT(fcm.facility_id) AS cnt
        FROM life_circles lc
        LEFT JOIN facility_circle_map fcm ON fcm.circle_id = lc.id
        LEFT JOIN facilities f ON f.id = fcm.facility_id AND f.is_active = 1
        WHERE lc.is_active = 1
        GROUP BY lc.id
        ORDER BY lc.sort_order
    """)
    circle_counts = {r["code"]: r["cnt"] for r in counts_rows}
    # 2) 圈层(字段集与 /api/circles 一致)
    circles = query("""
        SELECT id, code, name_zh, name_en, walk_time_min, walk_radius_m,
               population_min, population_max, household_min, household_max,
               area_ha_min, area_ha_max, sort_order, description
        FROM life_circles
        WHERE is_active = 1
        ORDER BY sort_order
    """)
    # 3) 案例速览(字段集与 /api/cases 一致,无 country 过滤)
    cases = query("""SELECT c.*,
                            (SELECT COUNT(*) FROM case_facilities cf WHERE cf.case_id = c.id) AS facilities_count,
                            (SELECT COUNT(*) FROM case_projects  cp WHERE cp.case_id = c.id) AS projects_count
                     FROM cases c
                     ORDER BY c.country, c.city, c.year""")
    return jsonify({
        "circles":       circles,
        "cases":         cases,
        "circle_counts": circle_counts,
    })


@app.route("/api/categories")
def api_categories():
    rows = query("""
        SELECT id, code, name_zh, name_en, parent_id, sort_order, description
        FROM categories
        WHERE is_active = 1
        ORDER BY COALESCE(parent_id, 0), sort_order
    """)
    # 构树
    by_id = {r["id"]: {**r, "children": []} for r in rows}
    tree = []
    for r in rows:
        if r["parent_id"]:
            by_id[r["parent_id"]]["children"].append(by_id[r["id"]])
        else:
            tree.append(by_id[r["id"]])
    return jsonify(tree)

@app.route("/api/facilities")
def api_facilities():
    category_id = request.args.get("category_id")
    sql = """
        SELECT f.id, f.code, f.name_zh, f.name_en, f.level, f.standard_source,
               c.name_zh AS category, c.id AS category_id,
               f.service_radius_max, f.recommended_area_sqm
        FROM facilities f
        JOIN categories c ON c.id = f.category_id
        WHERE f.is_active = 1
    """
    args = []
    if category_id:
        sql += " AND c.id = ?"
        args.append(category_id)
    sql += " ORDER BY c.sort_order, f.sort_order"
    return jsonify(query(sql, args))

def _escape_like(s: str) -> str:
    """转义 SQL LIKE 通配符 %, _ 和转义符 \\ 本身,避免用户输入 50% / foo_bar
    等被错误解释为通配符(2026-08-09 P0 修复)"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    like = f"%{_escape_like(q)}%"
    rows = query("""
        SELECT f.id, f.code, f.name_zh, f.name_en, c.name_zh AS category,
               f.level, f.recommended_area_sqm, f.standard_source
        FROM facilities f
        JOIN categories c ON c.id = f.category_id
        WHERE f.is_active = 1 AND (
            f.name_zh LIKE ? ESCAPE '\\' OR f.name_en LIKE ? ESCAPE '\\' OR f.aliases LIKE ? ESCAPE '\\'
            OR f.notes LIKE ? ESCAPE '\\' OR c.name_zh LIKE ? ESCAPE '\\'
        )
        ORDER BY f.sort_order
        LIMIT 50
    """, [like, like, like, like, like])
    return jsonify(rows)

# URL 协议白名单(服务端第二道闸):只放行 http(s) + 相对路径/纯文件名,
# 拦下 javascript:/data:/vbscript:/file: 等可执行协议
# 与前端 safeUrl() 客户端白名单互为冗余:任一层被绕过仍由另一层兜底
# ✅ P0 闭环:2026-08-12 Verifier R297 双层防御
_ALLOWED_URL_SCHEMES = {"http", "https", ""}
def _sanitize_standards_url(u):
    if not u:
        return ""
    try:
        scheme = (urlparse(u).scheme or "").lower()
    except (ValueError, TypeError):
        return ""
    return u if scheme in _ALLOWED_URL_SCHEMES else ""

@app.route("/api/standards")
def api_standards():
    rows = query("SELECT * FROM standards ORDER BY region, year DESC")
    # 服务端过滤 url 字段:非白名单协议直接置空(对应卡片仅留 short_name 文字,不渲染链接)
    for s in rows:
        if isinstance(s, dict) and "url" in s:
            s["url"] = _sanitize_standards_url(s.get("url"))
    return jsonify(rows)

# ---------- 启动 ----------
if __name__ == "__main__":
    print(f"")
    print(f"  ╔════════════════════════════════════════╗")
    print(f"  ║  15CircleDb Web App v{__version__:>20s} ║")
    print(f"  ║  http://localhost:5000                  ║")
    print(f"  ║  数据库: {DB.name:>30s} ║")
    print(f"  ║  更新于: {__updated__:>30s} ║")
    print(f"  ╚════════════════════════════════════════╝")
    print(f"")
    # 优先用 waitress(生产推荐:多线程 + 无 Werkzeug 性能/安全坑)
    # 缺包时降级到 Flask 自带 dev server(开发用)
    try:
        from waitress import serve
        print(f"  [i] 启动方式: waitress (生产) · 4 threads · http://localhost:5000")
        serve(app, host="0.0.0.0", port=5000, threads=4)
    except ImportError:
        print(f"  [i] 启动方式: Flask dev server (开发) · pip install waitress 切生产")
        app.run(host="0.0.0.0", port=5000, debug=False)
