"""
15CircleWeb 共享色板(单文件 Flask,无 app/ 子包;放项目根方便 from _colors import)
- 新增业态/圈层类别前请先查本表,严禁重复色
- 启动时强制跑 _check_uniqueness assert,色板重复直接抛错(开发期立即捕获)

✅ P2 闭环:2026-08-13 Verifier R301 — 11 业态色板去重 + 抽到独立模块
"""

# 案例业态体块图 11 大类色板
# 调整说明:业主食堂 #ff9500(留) + 全系餐饮 #ff7b00(深橙,避重复);
#          亲子休闲 #ff3b30(留) + 医疗健康 #ff6961(浅红/粉,避重复)
CASE_CATEGORY_COLORS = {
    "精神建筑":   "#af52de",  # 紫
    "业主食堂":   "#ff9500",  # 橙
    "文艺空间":   "#5856d6",  # 深紫蓝
    "运动休闲":   "#34c759",  # 绿
    "酒店民宿":   "#5ac8fa",  # 青
    "精品商业":   "#ff2d55",  # 粉
    "亲子休闲":   "#ff3b30",  # 红
    "创新教育":   "#ffcc00",  # 黄
    "全系餐饮":   "#ff7b00",  # 深橙(R301 调整:从 #ff9500 去重)
    "生活服务":   "#8e8e93",  # 灰
    "医疗健康":   "#ff6961",  # 浅红/粉(R301 调整:从 #ff3b30 去重)
}

# 一级分类 10 大类色板(圈层图例)
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


def _check_uniqueness():
    """色板唯一性 assert:重复色在 import 阶段就抛错,避免 massing 图例染色混乱。"""
    # 1) CASE_CATEGORY_COLORS 内部去重
    case_colors = list(CASE_CATEGORY_COLORS.values())
    case_seen = {}
    for k, v in CASE_CATEGORY_COLORS.items():
        if v in case_seen:
            raise AssertionError(
                f"[colors] CASE_CATEGORY_COLORS 重复色 #{v}: "
                f"'{case_seen[v]}' 与 '{k}' 都用 {v}。请二选一调整(参考 _colors.py 注释)。"
            )
        case_seen[v] = k
    # 2) CIRCLE_CATEGORY_COLORS 内部去重
    circle_seen = {}
    for k, v in CIRCLE_CATEGORY_COLORS.items():
        if v in circle_seen:
            raise AssertionError(
                f"[colors] CIRCLE_CATEGORY_COLORS 重复色 #{v}: "
                f"'{circle_seen[v]}' 与 '{k}' 都用 {v}。"
            )
        circle_seen[v] = k
    return True


# 模块加载即跑:开发期 fail-fast
_check_uniqueness()
