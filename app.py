"""
15CircleDb Web App
- 后端:Flask + SQLite
- 前端:单页应用 (SPA) + Tailwind CDN + Chart.js
- 启动:python app.py → http://localhost:5000
"""
__version__ = "1.0.0"
__updated__ = "2026-07-23"

import sqlite3
from pathlib import Path
from flask import Flask, jsonify, request, render_template, abort

BASE = Path(__file__).parent
# 库在上级目录
DB = BASE.parent / "15circledb.db"

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
        "version":         query("SELECT value FROM db_meta WHERE key='schema_version'")[0]["value"],
        "updated_at":      query("SELECT value FROM db_meta WHERE key='last_seed_date'")[0]["value"],
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
    sql = "SELECT * FROM cases"
    args = []
    if country:
        sql += " WHERE country = ?"
        args.append(country)
    sql += " ORDER BY country, city, year"
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
    return jsonify(case)

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
