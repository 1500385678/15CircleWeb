"""
15CircleDb Web App
- 后端:Flask + SQLite
- 前端:单页应用 (SPA) + Tailwind CDN + Chart.js
- 启动:python app.py → http://localhost:5000
"""
__version__ = "1.5.3"
__updated__ = "2026-07-24"

import sqlite3
from pathlib import Path
from flask import Flask, jsonify, request, render_template, abort

BASE = Path(__file__).parent
# 库在上级目录的上一级(适应 webapp/ 在 _scratch/ 或仓库根目录下的两种部署)
# 优先尝试 BASE.parent/15circledb.db,失败则 BASE.parent.parent/15circledb.db
_candidates = [BASE.parent / "15circledb.db", BASE.parent.parent / "15circledb.db"]
DB = next((p for p in _candidates if p.exists()), _candidates[0])

app = Flask(__name__, template_folder="templates", static_folder="static")

# ---------- 数据库连接 ----------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def query(sql, args=(), one=False):
    conn = get_db()
    cur = conn.execute(sql, args)
    rows = cur.fetchall()
    conn.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]

# ---------- 页面 ----------
@app.route("/")
def index():
    return render_template("index.html")

# ---------- API ----------
@app.route("/api/stats")
def api_stats():
    return jsonify({
        "standards":       query("SELECT COUNT(*) c FROM standards")[0]["c"],
        "life_circles":    query("SELECT COUNT(*) c FROM life_circles")[0]["c"],
        "climate_zones":   query("SELECT COUNT(*) c FROM climate_zones")[0]["c"],
        "facility_types":  query("SELECT COUNT(*) c FROM facility_types")[0]["c"],
        "categories":      query("SELECT COUNT(*) c FROM categories")[0]["c"],
        "facilities":      query("SELECT COUNT(*) c FROM facilities")[0]["c"],
        "facility_map":    query("SELECT COUNT(*) c FROM facility_circle_map")[0]["c"],
        "cases":           query("SELECT COUNT(*) c FROM cases")[0]["c"],
        "case_facilities": query("SELECT COUNT(*) c FROM case_facilities")[0]["c"],
        "case_projects":   query("SELECT COUNT(*) c FROM case_projects")[0]["c"],
        "app_version":     __version__,
        "app_updated":      __updated__,
        "db_version":      query("SELECT value FROM db_meta WHERE key='schema_version'")[0]["value"],
        "db_updated":      query("SELECT value FROM db_meta WHERE key='last_seed_date'")[0]["value"],
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

@app.route("/api/calculate")
def api_calculate():
    """反推配建清单:给定人口和圈层,返回必配数+总面积估算"""
    try:
        population = int(request.args.get("population", 50000))
    except ValueError:
        return jsonify({"error": "population 必须是整数"}), 400
    circles = request.args.get("circles", "15min,10min").split(",")
    priority = request.args.get("priority", "必配,宜配")

    placeholders_c = ",".join("?" for _ in circles)
    placeholders_p = ",".join("?" for _ in priority.split(","))

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
    args = [population, population] + circles + priority.split(",")
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
# 类目(11 大类:阿那亚) -> 颜色
CASE_CATEGORY_COLORS = {
    "精神建筑":   "#af52de",  # 紫
    "业主食堂":   "#ff9500",  # 橙
    "文艺空间":   "#5856d6",  # 深紫蓝
    "运动休闲":   "#34c759",  # 绿
    "酒店民宿":   "#5ac8fa",  # 青
    "精品商业":   "#ff2d55",  # 粉
    "亲子休闲":   "#ff3b30",  # 红
    "创新教育":   "#ffcc00",  # 黄
    "全系餐饮":   "#ff9500",  # 橙
    "生活服务":   "#8e8e93",  # 灰
    "医疗健康":   "#ff3b30",  # 红
}
# 一级分类 (10 大类) -> 颜色
CIRCLE_CATEGORY_COLORS = {
    "PUB": "#0066cc",  # 公共服务 - 苹果蓝
    "BIZ": "#ff9500",  # 商业服务 - 橙
    "CUL": "#af52de",  # 文化活动 - 紫
    "TRN": "#5ac8fa",  # 交通设施 - 青
    "GRN": "#34c759",  # 绿地与公共空间 - 绿
    "MUN": "#a3a3a3",  # 市政设施 - 灰
    "GOV": "#5856d6",  # 行政管理 - 深蓝紫
    "SMT": "#ff2d55",  # 智慧/智能化 - 粉
    "SAF": "#ff3b30",  # 公共安全 - 红
    "OTH": "#d1d1d6",  # 其他 - 浅灰
}


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

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    like = f"%{q}%"
    rows = query("""
        SELECT f.id, f.code, f.name_zh, f.name_en, c.name_zh AS category,
               f.level, f.recommended_area_sqm, f.standard_source
        FROM facilities f
        JOIN categories c ON c.id = f.category_id
        WHERE f.is_active = 1 AND (
            f.name_zh LIKE ? OR f.name_en LIKE ? OR f.aliases LIKE ?
            OR f.notes LIKE ? OR c.name_zh LIKE ?
        )
        ORDER BY f.sort_order
        LIMIT 50
    """, [like, like, like, like, like])
    return jsonify(rows)

@app.route("/api/standards")
def api_standards():
    return jsonify(query("SELECT * FROM standards ORDER BY region, year DESC"))

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
    app.run(host="0.0.0.0", port=5000, debug=False)
