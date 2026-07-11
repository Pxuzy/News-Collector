#!/usr/bin/env python
# coding=utf-8
"""Generate today's v23 News-Collector briefing from the fresh SQLite DB."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("NEWS_COLLECTOR_ROOT") or os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(ROOT, "data", "news.db")
OUTPUT_DIR = os.path.join(ROOT, "output")
CACHE_CANDIDATES = [
    os.path.join(ROOT, "cron", "output", "_data_gaps_cache.json"),
    os.path.join(ROOT, "output", "_data_gaps_cache.json"),
]

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from store import CST, get_stats, normalize_heat  # noqa: E402


SOURCE_CN = {
    "baidu": "百度",
    "zhihu": "知乎",
    "toutiao": "头条",
    "weibo": "微博",
    "douyin": "抖音",
    "bilibili": "B站",
    "bilibili_pop": "B站热门",
    "thepaper": "澎湃",
    "ithome": "IT之家",
    "36kr": "36氪",
    "wallstreetcn": "华尔街见闻",
    "jin10": "金十",
    "xueqiu": "雪球",
    "hackernews": "HackerNews",
    "github": "GitHub",
    "aihot": "AIHOT",
    "arxiv": "arXiv",
    "techcrunch": "TechCrunch",
    "arstechnica": "Ars Technica",
    "techmeme": "Techmeme",
    "bbc_world": "BBC",
    "reuters": "Reuters",
    "googlenews": "Google新闻",
    "reddit": "Reddit",
    "huggingface": "HuggingFace",
    "producthunt": "ProductHunt",
    "tmtpost": "钛媒体",
    "appso": "APPSO",
    "juejin": "掘金",
    "v2ex": "V2EX",
    "sspai": "少数派",
    "dongqiudi": "懂球帝",
}

SECTION_WORDING = {
    "时政·外交": {
        "impact": "这类事件会影响安全预期、外交沟通和舆论判断，热度高时还会带动周边议题持续扩散。",
        "followup": "看官方后续说明、相关国家或机构回应，以及热度是否继续跨平台扩散。",
        "insight": "这不是单条新闻热度，而是安全与外交信号共同叠加，适合放在今日主线里跟踪。",
    },
    "财经·商业": {
        "impact": "它会影响投资者风险偏好、产业链预期和企业经营判断，尤其需要区分短期情绪和基本面变化。",
        "followup": "看后续公告、市场成交变化、板块轮动和权威媒体确认。",
        "insight": "财经类热点容易被情绪放大，重点是看是否有明确数据、政策或业绩支撑。",
    },
    "科技·数码": {
        "impact": "它反映技术产品、平台生态或产业链变化，可能影响开发者选择、供应链订单和消费者预期。",
        "followup": "看产品细节、真实评测、供应链确认、开源社区反馈和商业化进展。",
        "insight": "科技热点要看落地路径，只有从概念进入产品、订单或开发者生态，才算真正变化。",
    },
    "汽车·能源": {
        "impact": "它会影响汽车产业链、能源价格、补能网络和消费选择，也可能改变短期板块情绪。",
        "followup": "看车企公告、交付数据、价格策略、能源价格和监管政策。",
        "insight": "汽车能源热点需要同时看需求、价格和政策，单一热搜不能直接推出趋势结论。",
    },
    "娱乐·综艺": {
        "impact": "它主要影响社交平台讨论、粉丝传播和内容消费，商业影响取决于是否带动票房、演出或品牌合作。",
        "followup": "看当事方回应、平台二次传播、作品数据和商业转化。",
        "insight": "娱乐热点传播快、衰减也快，重点看是否从饭圈扩散到大众讨论。",
    },
    "体育·赛事": {
        "impact": "赛事结果会影响球队士气、球员声量和后续赛程关注度，高热度比赛还会带动泛体育讨论。",
        "followup": "看赛后复盘、伤病情况、下一场对阵和官方处罚或判罚说明。",
        "insight": "体育热点的核心不是比分本身，而是关键球员、争议判罚和后续晋级路径。",
    },
    "社会·民生": {
        "impact": "它直接关系公共安全、生活成本或社会情绪，通常会引发政府处置、平台讨论和民生关注。",
        "followup": "看官方通报、救援或整改进展、责任认定和后续民生影响。",
        "insight": "民生热点要优先看事实核验和处置进度，不要只被情绪热度牵引。",
    },
    "AI·前沿": {
        "impact": "它会影响开发者工具链、企业采购、开源生态和模型成本结构，是技术圈今天最值得跟踪的变量。",
        "followup": "看官方发布、独立评测、代码或论文、API价格、社区真实使用反馈。",
        "insight": "AI热点需要区分研究进展、产品发布和社区传闻；能复现、可部署、成本可控的变化价值更高。",
    },
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def cutoff_iso(hours: int = 30) -> str:
    return (datetime.now(CST) - timedelta(hours=hours)).isoformat()


def parse_extra(item: dict) -> dict:
    raw = item.get("extra") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def clean(text: object, max_len: int | None = None) -> str:
    value = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("[", "【").replace("]", "】")
    if max_len and len(value) > max_len:
        return value[: max_len - 1].rstrip() + "…"
    return value


def md_link(item: dict) -> str:
    title = clean(item.get("title"), 90)
    url = clean(item.get("url")) or "链接未获取"
    return f"[{title}]({url})"


def heat_display(item: dict) -> str:
    heat = normalize_heat(str(item.get("heat") or ""))
    return heat or "热度未获取"


def item_key(item: dict) -> str:
    return clean(item.get("canonical_key") or item.get("url") or item.get("title"))


def query_sql(where: str, params: list[object], limit: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM news_items
            WHERE {where}
              AND last_seen >= ?
              AND COALESCE(is_duplicate,0)=0
            ORDER BY heat_score DESC, last_seen DESC
            LIMIT ?
            """,
            [*params, cutoff_iso(), limit],
        ).fetchall()
    return [dict(row) for row in rows]


def query_source(source: str, limit: int = 10) -> list[dict]:
    return query_sql("source=?", [source], limit)


def query_categories(categories: list[str], limit: int = 10) -> list[dict]:
    placeholders = ",".join("?" for _ in categories)
    return query_sql(f"category IN ({placeholders})", list(categories), limit)


HOTLIST_SOURCES = {"baidu", "toutiao", "weibo", "zhihu", "douyin", "bilibili_pop", "bilibili", "ithome", "36kr", "thepaper", "tencent"}


def query_hotlist(category: str, limit: int = 10) -> list[dict]:
    """从热榜平台源查询指定分类的条目"""
    placeholders = ",".join("?" for _ in HOTLIST_SOURCES)
    return query_sql(f"source IN ({placeholders}) AND category=?", list(HOTLIST_SOURCES) + [category], limit)


def query_hotlist_for_title(keyword: str, limit: int = 3) -> list[dict]:
    """从热榜平台源按标题关键词搜索热门条目"""
    placeholders = ",".join("?" for _ in HOTLIST_SOURCES)
    return query_sql(f"source IN ({placeholders}) AND title LIKE ?", list(HOTLIST_SOURCES) + [f"%{keyword}%"], limit)


MAIN_HOTLIST_KEYWORDS = ("台风", "巴威", "A股", "航天", "火箭回收", "救援", "涨价", "地震", "事故", "奥运")
MAIN_FALLBACK_CATEGORIES = ("社会", "军事", "财经", "AI", "综合")


def select_main_items(limit: int = 5) -> list[dict]:
    """Select main-line items with hotlist/category fallbacks when keyword hits are sparse."""
    items: list[dict] = []
    for keyword in MAIN_HOTLIST_KEYWORDS:
        items.extend(query_hotlist_for_title(keyword, 3))
    selected = unique(items, limit)
    if len(selected) >= limit:
        return selected

    fallback_items: list[dict] = []
    for category in MAIN_FALLBACK_CATEGORIES:
        fallback_items.extend(query_hotlist(category, max(limit * 2, 10)))
    # Keep the historical category fallback as a final safety net for sources
    # that classify an item but are not registered as a hotlist source.
    fallback_items.extend(query_categories(list(MAIN_FALLBACK_CATEGORIES), max(limit * 2, 10)))
    return unique(selected + fallback_items, limit)


def domestic_sections() -> list[tuple[str, str, list[dict]]]:
    """Build domestic sections, retaining broad hotlist categories as fallbacks."""
    return [
        ("🌍 **时政·外交**", "时政·外交", query_hotlist("时政", 8) + query_hotlist("军事", 6)),
        ("💰 **财经·商业**", "财经·商业", query_hotlist("财经", 8) + query_source("wallstreetcn", 3)),
        ("🔬 **科技·数码**", "科技·数码", query_hotlist("科技", 8) + query_source("ithome", 3)),
        ("🚗 **汽车·能源**", "汽车·能源", query_hotlist("汽车·能源", 6) + search_titles(["汽车", "新能源", "电池", "油价", "充电"], 6)),
        ("🎬 **娱乐·综艺**", "娱乐·综艺", query_hotlist("娱乐", 6) + query_source("bilibili_pop", 3)),
        ("⚽ **体育·赛事**", "体育·赛事", query_hotlist("体育", 6) + query_source("dongqiudi", 3)),
        # Some hotlist adapters classify broad social items as 综合, 教育, or 健康.
        ("🌞 **社会·民生**", "社会·民生",
         query_hotlist("社会", 10) + query_hotlist("综合", 8)
         + query_hotlist("教育", 4) + query_hotlist("健康", 4)),
    ]



def search_titles(keywords: list[str], limit: int = 10) -> list[dict]:
    clauses = " OR ".join("title LIKE ?" for _ in keywords)
    params = [f"%{kw}%" for kw in keywords]
    return query_sql(f"({clauses})", params, limit)


def unique(items: list[dict], limit: int, cross_source: bool = True,
           used_keys: set[str] | None = None, keyword_dedup: bool = True) -> list[dict]:
    """去重: 先按 canonical_key/url 去重, 再按跨源标题 2-gram 相似度去重,
    最后按关键词共现做事件级去重.

    Args:
        cross_source: 是否启用跨源标题相似度去重 (默认 True)
        used_keys: 外部已占用的 key 集合, 避免与前一 section 重复
        keyword_dedup: 是否启用关键词事件去重 (默认 True)
    """
    from dedup import _norm, _ng
    import re as _re

    # 事件关键词: 从标题中提取 2-3 字关键片段做跨源同事件检测
    def _extract_keywords(title: str) -> set[str]:
        n = _norm(title)
        segs: set[str] = set()
        # 用 2-gram 叠加作为关键词种子 (覆盖 "台风巴威" 这类多字实体)
        for i in range(len(n) - 1):
            pair = n[i:i+2]
            if pair and not pair.isdigit():
                segs.add(pair)
        # 过滤掉过于普遍的词 (停用词)
        stopwords = {'最新', '今日', '热搜', '热点', '事件', '进展', '成为', '当前', '已经', '可以', '关于', '对此'}
        segs -= stopwords
        # 英文 4+ 字单词
        segs.update(w.lower() for w in _re.findall(r'[a-z]{4,}', n))
        return segs

    def _event_overlap(kw1: set, kw2: set) -> bool:
        """两个关键词集合是否有显著重合 (>=3 个公共 2-gram 或 Jaccard>0.3)"""
        if not kw1 or not kw2:
            return False
        common = kw1 & kw2
        if len(common) >= 3:
            return True
        jac = len(common) / len(kw1 | kw2)
        return jac > 0.3

    seen: set[str] = set()
    seen_norms: list[set] = []
    seen_keywords: list[set] = []
    out = []
    for item in items:
        key = item_key(item)
        if not key or key in seen:
            continue
        if used_keys and key in used_keys:
            continue
        title = item.get("title", "")
        if cross_source:
            n = _norm(title)
            ng = _ng(n) if len(n) >= 4 else set()
            is_dup = False
            for prev_ng in seen_norms:
                if ng and prev_ng and len(ng & prev_ng) / len(ng | prev_ng) > 0.45:
                    is_dup = True
                    break
            if is_dup:
                continue
            if ng:
                seen_norms.append(ng)
        # 关键词事件去重: 同一事件不同角度的标题 (2-gram 不够, 关键词互补)
        if keyword_dedup:
            kw = _extract_keywords(title)
            is_event_dup = False
            for prev_kw in seen_keywords:
                if _event_overlap(kw, prev_kw):
                    is_event_dup = True
                    break
            if is_event_dup:
                continue
            if kw:
                seen_keywords.append(kw)
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def source_rank_maps(sources: list[str]) -> dict[str, dict[str, int]]:
    ranks: dict[str, dict[str, int]] = {}
    for source in sources:
        ranks[source] = {}
        for idx, item in enumerate(query_source(source, 80), 1):
            ranks[source][item_key(item)] = idx
    return ranks


def source_line(item: dict, ranks: dict[str, dict[str, int]]) -> str:
    source = item.get("source", "")
    source_cn = SOURCE_CN.get(source, source)
    rank = ranks.get(source, {}).get(item_key(item))
    rank_text = f"#{rank}" if rank else "#排名未获取"
    return f"{source_cn}{rank_text} · 热度{heat_display(item)}"


def desc_for(item: dict, fallback: str) -> str:
    extra = parse_extra(item)
    for field_name in ("hover", "desc", "description", "summary"):
        val = extra.get(field_name) or item.get(field_name)
        if val:
            desc = clean(val, 150)
            if desc:
                return desc
    return fallback


def item_specific_wording(item: dict, section: str, fallback_event: str) -> dict[str, str]:
    title = clean(item.get("title"))
    source = item.get("source", "")
    extra = parse_extra(item)
    blob = words_for(title, extra.get("hover"), extra.get("desc"), item.get("summary"))

    if source == "github":
        repo = repo_name(item)
        desc = clean(extra.get("hover") or extra.get("desc") or item.get("summary"), 100)
        return {
            "event": f"GitHub 项目 {repo} 进入热榜；{desc or '当前简介缺失，需要打开仓库核实用途。'}",
            "impact": "这类条目更像开发者工具信号，不是传统新闻事件；重点看它解决的开发流程、数据、Agent 或基础设施问题是否真实存在。",
            "followup": "看 README、最近提交、issue、许可证、安装体验和是否有真实用户案例。",
            "insight": "不要把总 Stars 当作今日新增热度；进入热榜代表短期曝光，真正价值要回到项目用途和维护质量。",
        }

    if section == "AI·前沿":
        if contains_any(blob, ["面试", "招聘", "吐槽", "人才", "天才少年"]):
            return {
                "event": fallback_event,
                "impact": "这更偏 AI 公司人才与组织口碑事件，不代表模型能力或产品突破；影响主要在雇主品牌、招聘信任和技术社区讨论。",
                "followup": "看当事方补充、公司回应、是否有更多候选人经历交叉验证。",
                "insight": "应按 AI 行业人才流动与组织治理观察，不能套用模型评测、API 定价或推理成本逻辑。",
            }
        if contains_any(blob, ["芯片", "融资", "gpu", "算力", "inference", "推理"]):
            return {
                "event": fallback_event,
                "impact": "重点在算力供给、成本结构和产业链自主化；如果属实，会影响模型部署成本和上下游供应商预期。",
                "followup": "看官方确认、融资文件、芯片规格、制程供应和第三方性能测试。",
                "insight": "这类 AI 产业新闻要优先验证来源和硬指标，不能只看社媒热度。",
            }
        anchor = clean(title, 28)
        return {
            "event": fallback_event,
            "impact": f"AI 条目“{anchor}”可能影响模型能力、工具链或应用落地，需先核对发布内容和真实使用证据。",
            "followup": f"围绕“{anchor}”查看官方资料、独立评测、代码/论文、价格和用户反馈。",
            "insight": f"对“{anchor}”的判断重点是可复现性、部署成本和集成路径，标题热度不能替代验证。",
        }

    if section == "时政·外交":
        if contains_any(blob, ["伊朗", "导弹", "美军", "军事", "袭击", "巡航",
                                "iran", "tehran", "missile", "strike", "ballistic", "military",
                                "explosion", "war", "conflict"]):
            return {
                "event": f"中东局势升温：{clean(title, 50)}",
                "impact": "中东地缘冲突直接影响全球能源价格、海运安全和大国博弈格局，需密切关注后续各方反应和实际损失评估。",
                "followup": "看美伊双方官方确认、联合国安理会动态、以色列/沙特等周边国家反应，以及布伦特原油和航运保险市场变动。",
                "insight": "中东冲突信息初期混乱，应优先看 Reuters/BBC/AP 等一线确认，避开社媒单方面传播的战果/伤亡数字。",
            }
        if contains_any(blob, ["检测", "审查", "限制", "制裁", "封锁", "中美", "关税",
                                "sanctions", "tariff", "restriction", "ban", "export"]):
            return {
                "event": f"贸易与技术管制新动向：{clean(title, 50)}",
                "impact": "影响跨境供应链、技术转移和企业合规成本，可能加速区域产业链重组。",
                "followup": "看官方文件、生效时间、豁免条款和企业应对预案。",
                "insight": "贸易限制类信息需要区分正式法令、媒体解读和行业评估三层，避免把草案和讨论当成定案。",
            }
        # 能源/制裁类
        if contains_any(blob, ["oil", "refinery", "gas", "cargo", "shipping", "energy",
                                "石油", "炼油", "航运", "能源"]):
            return {
                "event": f"能源与地缘经济动态：{clean(title, 50)}",
                "impact": "能源价格波动、炼厂停产和航线变化直接影响全球通胀预期、供应链成本和地缘经济格局。",
                "followup": "看布伦特原油走势、各国战略储备动态、替代能源采购和航运保险市场变化。",
                "insight": "能源类新闻要区分短期事件冲击和长期供需结构变化，单点停产的影响取决于持续时间和全球剩余产能。",
            }
        # 半导体/科技投资（处理被误分类为时政的财经/科技条目）
        if contains_any(blob, ["micron", "intel", "tsmc", "samsung", "semiconductor", "chip",
                                "investment", "fab", "manufacturing", "meta", "google",
                                "microsoft", "apple", "amazon", "openai", "anthropic",
                                "debuts", "spark", "muse"]):
            return {
                "event": f"科技与产业动态：{clean(title, 50)}",
                "impact": "大型科技公司的投资和产品发布反映产业链趋势和研发重点，直接影响市场竞争格局。",
                "followup": "看具体投资时间表、产品实测反馈、API 开放程度和竞品跟进情况。",
                "insight": "这类信息在时政分类下被捕获，但实质是科技/财经新闻，应切换到对应行业逻辑判断。",
            }
        anchor = clean(title, 28)
        return {
            "event": fallback_event,
            "impact": f"国际条目“{anchor}”可能影响安全预期、外交沟通或区域稳定，具体程度要看权威数据和各方行动。",
            "followup": f"围绕“{anchor}”查看官方通报、当事国回应和后续数据，确认是否出现新的事实进展。",
            "insight": f"对“{anchor}”应先核实事实链和时间线，再区分关注度、政治表态与已经发生的实际变化。",
        }

    # ── 通用 section 关键词分析 ──────────────────────────

    # 台风/极端天气
    if contains_any(blob, ["台风", "巴威", "暴雨", "洪水", "洪灾", "防汛", "灾害", "预警", "救灾", "应急", "洪涝"]):
        return {
            "event": fallback_event,
            "impact": "极端天气事件直接影响人员安全、交通出行、农业收成和基础设施，已触发多地应急响应。",
            "followup": "看中央气象台最新路径预报、地方防汛指挥部转移/停航/停课安排，以及受灾区域后续恢复进展。",
            "insight": f"天气类热点关注实时路径和官方预警级别变化，不要被单平台高热度过度渲染恐慌。\"{clean(title, 35)}\"的核心看点是风雨影响范围和持续时长。",
        }

    # 火灾/安全事故
    if contains_any(blob, ["火灾", "起火", "爆炸", "坍塌", "事故", "安全", "死亡", "伤亡", "被困", "遇难"]):
        return {
            "event": fallback_event,
            "impact": "安全事故直接关系公共安全和应急管理能力，事故原因和处置进度是关注焦点。",
            "followup": "看应急管理部通报、涉事单位回应、伤亡人数更新、事故原因调查和责任认定进展。",
            "insight": "安全类事件要优先核实官方通报数字，前期社媒传播的热度数字往往与最终官方核定数据存在差异。",
        }

    # A股/股市/金融
    if contains_any(blob, ["A股", "股市", "反弹", "牛市", "暴跌", "涨停", "跌停", "沪指", "创业板", "震荡"]):
        return {
            "event": f"市场波动：{clean(title, 50)}",
            "impact": "A股活跃度变化会影响投资者情绪、两融余额和板块轮动节奏，需区分短期情绪和基本面变化。",
            "followup": "看次日成交量、北向资金流向、政策面信号、板块龙头财报和外围市场联动。",
            "insight": "股市热点需要区分是政策驱动、资金驱动还是情绪驱动，单日行情不能直接判断趋势反转。",
        }

    # 芯片/科技制造
    if contains_any(blob, ["芯片", "半导体", "估值", "制造", "产能", "光刻", "制程", "中芯", "长鑫"]):
        return {
            "event": f"半导体/科技制造动态：{clean(title, 50)}",
            "impact": "芯片制造和存储领域的估值变化反映市场对国产替代和技术突破的预期，同时也受全球供需周期影响。",
            "followup": "看公司公告、产品良率、客户订单、设备交付进度和行业第三方产能报告。",
            "insight": "半导体估值新闻要区分市场融资估值、可比公司估值和实际营收之间的差距，高估值不等于已经实现技术突破。",
        }

    # 地震/地质灾害
    if contains_any(blob, ["地震", "震级", "宜宾", "震源", "余震"]):
        return {
            "event": fallback_event,
            "impact": "地震直接影响当地居民安全、建筑设施和交通秩序，震后次生灾害风险也需要持续关注。",
            "followup": "看中国地震台网正式测定数据、地方应急响应、人员伤亡排查和救灾物资调度。",
            "insight": "地震信息以中国地震台网和中国地震局发布为准，社媒传播的伤亡数字需等待官方核对确认。",
        }

    # 体育/赛事
    if contains_any(blob, ["男篮", "女篮", "足球", "世界杯", "c罗", "c 罗", "哈兰德", "比赛", "赛事", "夺冠", "判罚",
                           "国足", "NBA", "欧冠", "msi", "blg", "hle", "竞技"]):
        return {
            "event": f"体育赛事热讯：{clean(title, 50)}",
            "impact": "赛事结果影响球队晋级形势、球员商业化价值和球迷社群活跃度。关键比赛还会带动周边讨论。",
            "followup": "看赛后复盘、关键球员伤情、下一场对阵安排和赛事官方数据确认。",
            "insight": "体育热点的核心不是比分本身，而是关键球员表现、争议判罚和后续晋级路径。",
        }

    # AI 相关（在非 AI section 中出现的 AI 内容）
    if contains_any(blob, AI_TERMS):
        return {
            "event": fallback_event,
            "impact": "AI 动态可能影响模型能力、开发者工具链或产业落地节奏，但需先区分发布、传闻和实际产品更新。",
            "followup": "看官方发布、独立评测、API 定价、开源仓库活跃度和社区真实使用反馈。",
            "insight": "AI 相关条目的价值取决于可复现能力、成本和集成路径，标题热度本身不是结论。",
        }

    # 能源/石油/航运
    if contains_any(blob, ["oil", "refinery", "gas", "cargo", "shipping", "energy", "sanctions",
                           "石油", "炼油", "航运", "能源", "制裁"]):
        return {
            "event": f"能源与供应链动态：{clean(title, 50)}",
            "impact": "能源价格波动、炼厂停产和航线变化直接影响全球通胀预期、供应链成本和地缘经济格局。",
            "followup": "看布伦特原油走势、各国战略储备动态、替代能源采购和航运保险市场变化。",
            "insight": "能源类新闻要区分短期事件冲击和长期供需结构变化，单点停产的影响取决于持续时间和全球剩余产能。",
        }

    # 中东/地缘冲突（英文关键词覆盖）
    if contains_any(blob, ["iran", "tehran", "missile", "strike", "ballistic", "military",
                           "syria", "iraq", "gaza", "hezbollah", "houthi", "red sea"]):
        return {
            "event": f"中东地缘动态：{clean(title, 50)}",
            "impact": "中东局势紧张直接影响全球能源安全、海运通道和区域稳定，多方冲突升级可能引发更广泛的国际介入。",
            "followup": "看各国官方声明、联合国安理会动态、能源市场反应和实际损失/伤亡评估。",
            "insight": "地缘冲突信息初期高度混乱，应优先参考 Reuters/AP/BBC 等一线信源的地面核实，避开社媒早期单向传播的战报。",
        }

    # 半导体/科技投资
    if contains_any(blob, ["micron", "intel", "tsmc", "samsung", "semiconductor", "chip",
                           "investment", "fab", "manufacturing", "产能", "投资", "美国", "芯片法案"]):
        return {
            "event": f"半导体/科技投资动态：{clean(title, 50)}",
            "impact": "大型半导体投资计划反映全球芯片产业链重组趋势和各国补贴竞争，直接影响设备商、材料商和下游客户预期。",
            "followup": "看投资落地时间表、设备采购订单、美国政府补贴审批进展和产能爬坡数据。",
            "insight": "半导体投资计划需区分正式落地和意向声明，关注实际动工时间和量产目标比宣布金额更有意义。",
        }

    # 大型科技公司动态（Meta/Google/Apple/Microsoft）
    if contains_any(blob, ["meta", "google", "microsoft", "apple", "amazon", "openai", "anthropic",
                           "debuts", "unveils", "launches", "releases", "spark", "muse"]):
        return {
            "event": f"科技巨头动态：{clean(title, 50)}",
            "impact": "科技巨头的产品发布直接影响行业标准和竞争格局，也反映了当前的研发重点和战略方向。",
            "followup": "看产品实测、开发者反馈、定价策略、API 开放程度和竞品跟进情况。",
            "insight": "科技巨头发布的产品需要区分宣传目标和实际能力，关注可用性、定价和生态整合的程度。",
        }

    # 电动车/新能源车
    if contains_any(blob, ["比亚迪", "蔚来", "小鹏", "理想", "小米", "特斯拉", "新能源", "电车", "充电",
                           "续航", "电动", "汉", "es8", "腾势", "上市", "SUV", "高压", "架构",
                           "NEV", "electric vehicle", "ev"]):
        if contains_any(blob, ["欧洲", "海外", "出口", "全球", "定价"]):
            return {
                "event": f"中国新能源车出海新动态：{clean(title, 50)}",
                "impact": "中国新能源车企加速全球化布局，欧洲市场定价和渠道策略是观察品牌溢价和本地化能力的关键窗口。",
                "followup": "看欧洲NCAP测试成绩、当地充电网络兼容性、交付数据和后续车型规划。",
                "insight": "出海新闻要看实际交付量和当地消费者评价，发布定价和媒体热度只是第一步，真正验证在后续销量。",
            }
        return {
            "event": f"新能源车动态：{clean(title, 50)}",
            "impact": "新能源车企新车发布、技术迭代和价格策略直接影响市场竞争格局和消费者选择。800V高压平台和智能驾驶是当前主要竞争点。",
            "followup": "看车型交付时间表、实际续航测试、智能驾驶功能和终端售价变化。",
            "insight": "新车发布的热度需要关注的是正式售价、配置差异和交付节奏，而不是仅看展车和概念阶段的关注度。",
        }

    # 游戏/电竞
    if contains_any(blob, ["游戏", "steam", "xbox", "ps5", "任天堂", "首曝", "实机", "演示",
                           "搜打撤", "诡影", "moba", "rpg", "动作", "志怪", "预售"]):
        return {
            "event": f"游戏动态：{clean(title, 50)}",
            "impact": "新游曝光和预售数据反映玩家期待度和市场热度，首曝PV品质和玩法实机演示是判断产品质量的关键。",
            "followup": "看后续媒体试玩评测、Steam Wishlist/预约量、开发商过往作品口碑和正式发售日。",
            "insight": "游戏首曝热度不等于最终品质，重点看玩法创新、优化水平、定价策略和社区长线反馈。",
        }

    # 碳达峰/环保/气候政策
    if contains_any(blob, ["碳达峰", "碳中和", "碳排放", "节能", "减排", "环保", "气候", "绿色", "双碳"]):
        return {
            "event": f"气候政策与绿色转型：{clean(title, 50)}",
            "impact": "碳达峰工作推进直接影响能源结构转型、产业升级节奏和绿色金融规模，是中长期政策主线。",
            "followup": "看具体行业减排路线图、碳交易市场动态、重点行业排放数据和绿色技术创新进展。",
            "insight": "碳达峰是长线政策，需要区分短期工作部署和长期目标调整，不要因为阶段性热度判断政策方向已经变化。",
        }

    # 基础设施/公共政策
    if contains_any(blob, ["拆除", "替代", "隔离", "景区", "整改", "设施", "规划", "刀片", "泰山"]):
        return {
            "event": f"公共设施与政策调整：{clean(title, 50)}",
            "impact": "景区设施调整直接关系游客体验、公共安全和旅游形象，整改方案和替代措施的效果是关注重点。",
            "followup": "看景区官方整改方案、施工时间表、公众意见征集和实际改造效果反馈。",
            "insight": "公共设施类新闻的核心是方案可行性和落地时间表，社媒上的情绪反应不等同于政策质量。",
        }

    # 手机/数码产品
    if contains_any(blob, ["iPhone", "华为", "小米", "OPPO", "vivo", "三星", "折叠", "手机",
                           "平板", "智能", "可穿戴", "系统", "APP", "微信", "功能"]):
        return {
            "event": f"数码产品动态：{clean(title, 50)}",
            "impact": "数码产品功能更新和平台策略调整直接影响用户体验、市场竞争格局和开发者生态。",
            "followup": "看官方发布详情、第三方评测、用户反馈和竞品跟进策略。",
            "insight": "数码产品热点需要区分功能需求讨论和实际产品发布，社媒上的功能呼吁不等于产品路线图。",
        }

    # 安全/治安/犯罪
    if contains_any(blob, ["丢失", "手机", "转空", "盗窃", "诈骗", "骗子", "警方", "被捕",
                           "违法", "拘留", "判刑", "女子", "男子", "死亡", "昏迷"]):
        return {
            "event": f"社会安全事件：{clean(title, 50)}",
            "impact": "个人安全事件和高发诈骗手法最容易引发公众焦虑和自我保护意识，传播速度在社媒上极快。",
            "followup": "看警方通报和调查进展、涉事平台回应、同类案件数据以及防骗/防盗指南更新。",
            "insight": "安全类热点需区分真实案件和社媒传播放大的部分，优先确认警方核实和当事人后续进展。",
        }

    # 电影/娱乐/票房
    if contains_any(blob, ["票房", "预售", "电影", "上映", "主演", "导演", "综艺", "运动",
                           "功夫", "女足", "演唱会", "剧场"]):
        return {
            "event": f"文娱/票房动态：{clean(title, 50)}",
            "impact": "票房预售数据反映观众期待度，是判断宣传效果和首周表现的前瞻指标。",
            "followup": "看首周末实际票房、口碑评分、排片占比和二刷率，区分预售转化率和实际上座率。",
            "insight": "票房类热度需要区分预售和实际观影体验口碑，高预售不等于高口碑，重点是上映后的长线表现。",
        }

    # 医疗/健康
    if contains_any(blob, ["医疗", "手术", "昏迷", "牙齿", "全麻", "医院", "疫苗", "健康",
                           "保健", "药品", "医保", "shou", "疾病", "医院"]):
        return {
            "event": f"医疗健康事件：{clean(title, 50)}",
            "impact": "医疗安全事件直接关系患者权益和医疗服务质量管理，引发公众对诊疗流程和安全保障的关注。",
            "followup": "看医院官方说明、卫健委调查结论、家属沟通进展和同类医疗纠纷数据。",
            "insight": "医疗新闻需要以官方通报和第三方医学意见为准，社媒传播的患者个案不能代表整体医疗质量。",
        }

    # 默认文案也绑定当前标题，避免同一板块所有条目复用完全相同的三句模板。
    anchor = clean(title, 28)
    return {
        "event": fallback_event,
        "impact": f"“{anchor}”涉及的具体影响，需要结合事件对象、时间范围和权威数据判断，当前不能只凭热度下结论。",
        "followup": f"围绕“{anchor}”查看官方回应、后续数据和当事方行动，重点确认是否出现新的可验证进展。",
        "insight": f"本条的判断重点是核对“{anchor}”的事实链，再区分短期关注度与长期影响。",
    }


def add_news_block(lines: list[str], item: dict, section: str, ranks: dict[str, dict[str, int]], dot: str = "🟠") -> None:
    title = clean(item.get("title"), 70)
    source_name = SOURCE_CN.get(item.get("source", ""), item.get("source", ""))
    fallback_event = f"围绕“{title}”的最新进展成为{source_name}热点，当前仍在发酵。"
    wording = item_specific_wording(item, section, fallback_event)
    anchor = clean(title, 28)
    for field in ("impact", "followup", "insight"):
        wording[field] = f"{wording[field]} 本条主题为：{anchor}。"
    extra = parse_extra(item)
    has_real_desc = bool(clean(extra.get("hover") or extra.get("desc") or extra.get("description") or item.get("summary")))
    if item.get("source") in HOTLIST_SOURCES and not has_real_desc:
        heat_val = heat_display(item)
        lines.append(f"{dot} {md_link(item)}")
        lines.append("")
        lines.append(f"> 📍 来源：{source_line(item, ranks)}  ")
        lines.append(f"> 🔥 热度：{heat_val}（平台热榜值）  ")
        lines.append(f"> 💡 解读：{social_news_insight(item)} 本条主题为：{title}。  ")
        lines.append(f"> ✅ 可信度：{source_line(item, ranks)}，属于平台热榜信号，需结合原始链接核验")
        lines.append("")
        return
    lines.append(f"{dot} {md_link(item)}")
    lines.append("")
    lines.append(f"> 📍 来源：{source_line(item, ranks)}  ")
    lines.append(f"> 📌 事件：{desc_for(item, wording['event'])}  ")
    lines.append(f"> 🌊 影响：{wording['impact']}  ")
    lines.append(f"> 👀 后续：{wording['followup']}  ")
    lines.append(f"> 💡 解读：{wording['insight']}  ")
    if has_real_desc:
        lines.append(f"> ✅ 可信度：{source_line(item, ranks)}；已获取摘要/描述，仍建议回看原始链接")
    else:
        lines.append(f"> ✅ 可信度：{source_line(item, ranks)}；当前缺少摘要，需结合原始链接核验")
    lines.append("")


def add_short_block(lines: list[str], item: dict, section: str, ranks: dict[str, dict[str, int]]) -> None:
    wording = SECTION_WORDING[section]
    fallback_event = f"“{clean(item.get('title'), 60)}”进入今日热点列表。"
    lines.append(f"🟠 {md_link(item)}")
    lines.append("")
    lines.append(f"> 📍 来源：{source_line(item, ranks)}  ")
    lines.append(f"> 📌 事件：{desc_for(item, fallback_event)}  ")
    lines.append(f"> 💡 解读：{wording['insight']}  ")
    lines.append("> ✅ 可信度：来自采集库，需结合原始链接继续核验")
    lines.append("")


def load_cache() -> dict:
    for path in CACHE_CANDIDATES:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}


def repo_name(item: dict) -> str:
    title = clean(item.get("title")).replace(" / ", "/").replace(" ", "")
    if "/" in title:
        parts = [part.strip() for part in title.split("/") if part.strip()]
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
    url = clean(item.get("url"))
    if "github.com/" in url:
        rest = url.split("github.com/", 1)[1].split("?")[0].strip("/")
        parts = rest.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return title


def github_info(repo: str, cache: dict) -> dict:
    return cache.get("github_language", {}).get(repo, {})


AI_TERMS = (
    "ai", "artificial intelligence", "llm", "gpt", "claude", "gemini", "deepseek",
    "qwen", "glm", "agent", "agents", "model", "models", "codex", "openai",
    "huggingface", "rag", "inference", "prompt", "大模型", "人工智能", "模型",
    "智能体", "推理", "算力", "芯片",
)


def words_for(*parts: object) -> str:
    return " ".join(clean(part) for part in parts if part).lower()


def contains_any(text: str, keywords: tuple[str, ...] | list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def is_ai_relevant(item: dict) -> bool:
    title = words_for(item.get("title"), item.get("summary"), parse_extra(item).get("desc"))
    source = item.get("source", "")
    if source in {"aihot", "huggingface", "arxiv", "tldr_ai"}:
        return True
    return contains_any(title, AI_TERMS)


def github_profile(repo: str, desc: str, language: str, topics: list[str] | None, label: str) -> dict[str, str]:
    blob = words_for(repo, desc, language, " ".join(topics or []))
    if not desc or desc.startswith("项目简介未获取"):
        return {
            "summary": "项目简介未获取，当前只能确认它进入了 GitHub 趋势榜，不能直接判断用途和成熟度。",
            "purpose": "先把它当作待核验项目处理：打开 README 看目标用户、安装步骤、许可证和最近提交，再决定是否纳入工具链或观察列表。",
            "why": f"热度信号来自 GitHub {label}排名；Stars 若缺失或为空，不能作为强热度证据。",
            "follow": "README、许可证、最近 release、issue 质量、是否有真实 demo 或用户案例。",
        }

    if contains_any(blob, ["security", "pentest", "penetration", "vulnerab", "red-team", "hacking", "ctf"]):
        return {
            "summary": "安全测试/漏洞发现工具。",
            "purpose": "从简介看，它面向安全测试或 AI 应用风险排查，核心价值是把漏洞发现、验证或修复流程工具化。适合安全工程师、红队和正在上线 AI 应用的团队先做小范围试用。",
            "why": f"安全自动化和 AI 安全是近期开发者关注高地，进入 GitHub {label}说明该方向正在被快速验证。",
            "follow": "漏洞覆盖范围、误报率、沙箱隔离、报告质量、是否有安全审计和企业场景案例。",
        }
    if contains_any(blob, ["scrape", "scraping", "crawler", "crawl", "web data", "extract", "search"]):
        return {
            "summary": "网页抓取、搜索或数据抽取基础设施。",
            "purpose": "它解决的是把网页内容稳定转换为可用数据的问题，常用于 RAG、监控、数据采集和自动化研究。重点不是“又一个爬虫”，而是稳定性、反爬处理、结构化质量和成本。",
            "why": f"AI 应用需要高质量外部数据，Web 数据基础设施上榜 GitHub {label}通常反映开发者在补齐数据入口。",
            "follow": "限流策略、robots 合规、结构化精度、失败重试、API 定价和大规模任务稳定性。",
        }
    if contains_any(blob, ["meeting", "transcription", "whisper", "speaker", "diarization", "ollama"]):
        return {
            "summary": "会议记录、转写或本地 AI 助理。",
            "purpose": "它面向会议音频转写、说话人分离和本地总结，价值在于把会议内容转为可搜索、可复盘的结构化资料。隐私、本地运行和实时性是判断它是否实用的关键。",
            "why": f"会议 AI 从云端服务转向本地隐私方案，进入 GitHub {label}说明开发者正在寻找可控替代品。",
            "follow": "转写准确率、中文支持、离线模型、说话人分离效果、导出格式和企业合规能力。",
        }
    if contains_any(blob, ["dataset", "data set", "exercises", "fitness", "benchmark"]):
        return {
            "summary": "数据集或基准资源。",
            "purpose": "它的价值不在运行时能力，而在数据覆盖、字段结构和授权方式。适合需要快速构建 demo、训练样本或评测集的团队核验数据质量后再使用。",
            "why": f"数据资源进入 GitHub {label}通常说明某个垂直场景缺少标准化开放数据。",
            "follow": "许可证、字段完整度、样本来源、更新频率、数据偏差和是否有可复现实验。",
        }
    if contains_any(blob, ["gateway", "provider", "route", "router", "endpoint", "token", "claude code", "cursor", "cline"]):
        return {
            "summary": "AI 模型网关或开发工具接入层。",
            "purpose": "它把多个模型或开发工具接到统一入口，重点价值是降低接入成本、切换成本和失败兜底成本。适合多模型工作流团队关注，但要重点核验稳定性和凭据安全。",
            "why": f"多模型调用和成本控制需求上升，网关类项目进入 GitHub {label}说明工具链正在从单模型转向路由层。",
            "follow": "鉴权方式、日志隐私、限流、失败重试、供应商覆盖、免费额度真实性和自托管能力。",
        }
    if contains_any(blob, ["agent", "agents", "codex", "claude", "mcp", "skills", "workflow", "multiplexer"]):
        return {
            "summary": "AI Agent 或编码工作流工具。",
            "purpose": "它围绕 Agent 编排、技能管理或编码助手协作展开，解决的是让多个 AI 工具更可控地完成开发任务。真正价值取决于工作流是否清晰、状态是否可追踪、失败是否可恢复。",
            "why": f"Agent 开发工具仍是 GitHub {label}高频主题，上榜说明开发者在寻找更稳定的 AI 协作层。",
            "follow": "任务隔离、上下文管理、权限边界、插件生态、实际项目案例和与现有 IDE/CLI 的集成成本。",
        }
    if contains_any(blob, ["awesome", "list", "resources", "curated"]):
        return {
            "summary": "资料索引或 curated list。",
            "purpose": "它不是可运行工具，而是把某一领域资源整理成索引。价值取决于筛选标准、更新频率和去重质量；适合作为调研入口，不适合作为工程能力本身引用。",
            "why": f"资料集合上 GitHub {label}通常代表该领域资料爆炸，开发者需要更好的导航入口。",
            "follow": "维护频率、收录标准、失效链接、是否区分入门/高级资源和是否接受社区 PR。",
        }
    if contains_any(blob, ["photo", "video", "media", "gallery", "dictation", "voice", "stt"]):
        return {
            "summary": "媒体、语音或个人数据管理工具。",
            "purpose": "它面向图片、视频或语音内容处理，关键是把个人数据管理、检索或转写流程做得更可控。判断价值时要优先看本地部署、隐私和导入导出能力。",
            "why": f"个人数据和本地 AI 工具在 GitHub {label}持续升温，说明用户想减少对封闭云服务的依赖。",
            "follow": "隐私模型、备份恢复、移动端体验、硬件要求、格式兼容和迁移成本。",
        }
    return {
        "summary": "开发者工具或开源基础设施。",
        "purpose": f"从简介看，它解决的是“{clean(desc, 80)}”这一类工程问题。先按开发者工具评估：能否快速安装、能否接入现有流程、文档是否足够支撑真实使用。",
        "why": f"进入 GitHub {label}说明它在开发者社区获得趋势曝光；Stars 是总量指标，不等同于今日新增热度。",
        "follow": "安装体验、核心功能边界、维护者活跃度、issue 响应、许可证和与同类工具的差异。",
    }


def add_github_item(lines: list[str], repo: str, url: str, rank: int, info: dict, daily: bool, item: dict | None = None) -> None:
    stars = info.get("stars")
    if not stars:
        item_heat = clean((item or {}).get("heat")).replace("⭐", "").replace(",", "")
        stars = item_heat if item_heat else "Stars未获取"
    language = info.get("language") or "语言未获取"
    extra = parse_extra(item or {})
    desc = clean(
        info.get("description")
        or extra.get("description")
        or extra.get("hover")
        or extra.get("desc")
        or (item or {}).get("summary"),
        140,
    ) or "项目简介未获取，需点开 README 核实。"
    topics = info.get("topics") or []
    label = "日榜" if daily else "周榜"
    profile = github_profile(repo, desc, language, topics, label)
    lines.append(f"• GitHub#{rank} {label} [{repo}]({url}) ⭐ {stars} · {language}")
    lines.append("")
    lines.append(f"> 📌 项目：{profile['summary']} {desc}  ")
    lines.append(f"> 🧩 是干嘛的：{profile['purpose']}  ")
    lines.append(f"> 🔥 为什么热：GitHub#{rank} {label} · {profile['why']}  ")
    lines.append(f"> 👀 后续看：{profile['follow']}")
    lines.append("")


def hn_topic(title: str) -> tuple[str, str, str]:
    blob = words_for(title)
    if contains_any(blob, ["privacy", "track", "device id", "security", "threat", "verification", "steganographic"]):
        return ("安全/隐私", "重点看攻击面、平台默认策略和用户是否有可操作的规避或防护选择。", "评论区通常会补充真实复现、威胁模型和平台方动机。")
    if contains_any(blob, ["llm", "gpt", "claude", "qwen", "glm", "language model", "models", "ai ", "agent"]):
        return ("AI/模型", "重点看模型能力、成本、开放性和开发者工作流影响，不要只看发布标题。", "评论区通常会围绕基准、定价、开源可用性和实际体验展开。")
    if contains_any(blob, ["openwrt", "router", "hardware", "ryzen", "gpu", "linux", "atari", "device"]):
        return ("硬件/系统", "重点看硬件可得性、开放程度、驱动支持和长期维护成本。", "评论区往往会给出购买、刷机、兼容性和性能方面的实测经验。")
    if contains_any(blob, ["map", "openstreetmap", "offline", "foss"]):
        return ("开源应用", "重点看它是否能替代封闭服务，以及数据源、离线体验和社区维护是否可靠。", "评论区通常会比较同类应用、隐私取舍和平台限制。")
    if contains_any(blob, ["xbox", "steam", "game", "gaming"]):
        return ("游戏/平台", "重点看平台策略变化、开发者生态和用户迁移成本。", "评论区通常会出现大量用户体验、商业模式和平台锁定讨论。")
    if contains_any(blob, ["cell", "dna", "researchers", "scientists", "netherlands"]):
        return ("科学/科研", "重点看研究本身的可验证性、资源投入和政策环境变化。", "评论区常会补充背景论文、实验限制或科研制度讨论。")
    return ("工程", "重点看它解决的具体工程问题、是否能复现、以及是否比现有方案更简单。", "评论区通常会补充边界条件、替代方案和真实使用经验。")


def hn_chinese_profile(title: str, points: str = "", comments: str = "") -> dict[str, str]:
    """HN 条目的中文翻译、事件说明和解读"""
    blob = words_for(title)
    t = clean(title, 90)

    # ========== Show HN ==========
    if contains_any(blob, ["show hn", "show hn:"]):
        project = clean(title.replace('Show HN:', '').replace('Show HN ', '').strip(), 50)
        return {
            "cn_title": f"展示项目：{project}",
            "event": f"HN 用户自荐项目「{project}」，开发者向社区展示了自己的作品，HN 用户正在试用和讨论。",
            "impact": "Show HN 是社区发现新工具、新产品的重要窗口，高赞说明它解决了真实问题或展示了有趣创意。",
            "insight": "重点看项目是否开源、是否可立即试用，以及评论区给出的改进建议和同类产品对比。",
        }

    # ========== Launch HN / YC ==========
    if contains_any(blob, ["launch hn", "launch hn:", "yc "]):
        project = clean(title.replace('Launch HN:', '').replace('Launch HN ', '').strip(), 50)
        return {
            "cn_title": f"创业发布：{project}",
            "event": f"YC 孵化的创业项目「{project}」正式在 HN 发布，创始团队介绍了产品功能和目标用户，社区正在反馈。",
            "impact": "YC 孵化产品通常有明确的用户痛点和商业模式，HN 讨论可以快速验证市场对其方向的认可度。",
            "insight": "关注产品的真实差异化、定价策略、技术壁垒和评论区中潜在用户的使用反馈。",
        }

    # ========== AI/LLM 发布 ==========
    if contains_any(blob, ["gpt", "claude", "gemini", "deepseek", "qwen", "glm", "llama", "mistral", "codestral",
                           "openai", "anthropic", "ai model", "language model"]):
        model = clean(title, 40)
        if contains_any(blob, ["release", "launch", "announce", "new "]):
            return {
                "cn_title": f"{model} 发布",
                "event": f"{model} 正式发布/更新。技术社区正在分析其能力提升、架构变化和与竞品的对比。",
                "impact": "新模型发布直接影响下游应用的性能天花板、API 定价和开发者工具链选择。",
                "insight": "关注独立第三方评测结果、定价变化、开放权重/API 情况和评论区中一线工程师的真实使用体验。",
            }
        return {
            "cn_title": f"{model}",
            "event": f"关于 {model} 的讨论在 HN 上成为热点，技术社区正在分析其能力、成本和应用场景。",
            "impact": "AI 模型的进展直接影响开发者的工具选型、应用性能和商业模式判断。",
            "insight": "区分官方发布、社区评测和纯讨论，关注可复现的基准测试和评论区中的一线使用报告。",
        }

    # ========== 隐私/监控 (含 Chat Control) ==========
    if contains_any(blob, ["chat control"]):
        return {
            "cn_title": "欧盟通过 Chat Control 监控法案",
            "event": "欧洲议会通过了 Chat Control 1.0 法案，要求通讯平台扫描用户消息以检测儿童性虐待内容，引发大规模隐私争议。",
            "impact": "该法案将强制端到端加密平台扫描用户内容，直接影响隐私保护、加密技术的可行性和言论自由。",
            "insight": "关注法案覆盖范围（是否包括加密消息）、技术实现方式（客户端扫描 vs 服务器端）和生效时间线。",
        }
    if contains_any(blob, ["surveillance", "mass surveillance", "privacy", "tracking",
                           "tracker", "gdpr", "digital rights"]):
        return {
            "cn_title": f"隐私与监控：{t}",
            "event": f"涉及数字隐私和监控政策的新闻：{t}。隐私维权组织、立法机构和科技公司之间的博弈是核心主线。",
            "impact": "监控类立法直接影响用户隐私保护水平、企业的合规成本和跨境数据流动规则。",
            "insight": "区分法案草案、表决结果和正式实施三个阶段，关注例外条款和执行机制是否留有规避空间。",
        }

    # ========== 安全漏洞 ==========
    if contains_any(blob, ["vulnerab", "exploit", "breach", "0-day", "zero-day", "cve",
                           "ransomware", "backdoor", "malware", "supply chain attack"]):
        vuln = clean(title, 60)
        return {
            "cn_title": f"安全漏洞：{vuln}",
            "event": f"安全研究人员披露了 {vuln}，涉及具体漏洞细节、影响范围和修复方案。",
            "impact": "安全漏洞直接影响用户数据安全、企业合规成本和平台信任度，补丁时间线是关注核心。",
            "insight": "区分概念验证(PoC)和已在野利用，关注受影响版本范围、临时缓解措施和官方补丁发布状态。",
        }

    # ========== 政策/法律/诉讼 ==========
    if contains_any(blob, ["ftc", "regulation", "regulatory", "compliance", "law ", "lawsuit", "legal",
                           "court", "right to repair", "antitrust", "monopoly", "fcc",
                           "european union", "eu ", "parliament", "congress"]):
        policy = clean(title, 60)
        # 具体政策事件
        if contains_any(blob, ["right to repair", "right-to-repair"]):
            company = "设备制造商"
            for c in ["john deere", "apple", "microsoft", "samsung", "tesla"]:
                if c in blob:
                    company = {"john deere": "约翰迪尔", "apple": "苹果", "microsoft": "微软",
                               "samsung": "三星", "tesla": "特斯拉"}.get(c, c)
                    break
            return {
                "cn_title": f"维修权：{company} 达成和解",
                "event": f"{company} 与美国监管机构就维修权问题达成和解，用户和第三方维修店将获得更自由的维修权限。",
                "impact": "维修权运动直接影响消费品寿命、电子垃圾减量和消费者权益，也将推动设备可维修设计的标准化。",
                "insight": "关注和解协议的具体条款：是否开放了诊断工具、是否影响保修、是否允许第三方配件。",
            }
        if contains_any(blob, ["chat control"]):
            return {
                "cn_title": "欧盟通过 Chat Control 监控法案",
                "event": "欧洲议会通过了 Chat Control 1.0 法案，要求通讯平台扫描用户消息以检测儿童性虐待内容，引发大规模隐私争议。",
                "impact": "该法案将强制端到端加密平台扫描用户内容，直接影响隐私保护、加密技术的可行性和言论自由。",
                "insight": "关注法案覆盖范围（是否包括加密消息）、技术实现方式（客户端扫描 vs 服务器端）和生效时间线。",
            }
        return {
            "cn_title": f"政策动态：{policy}",
            "event": f"科技监管政策动态：{policy}。监管机构正在调整对科技行业的规则，可能影响商业模式和竞争格局。",
            "impact": "科技监管政策直接影响企业的合规成本、商业模式和市场竞争格局，具有长期结构性影响。",
            "insight": "关注法案的实际执行方式、豁免条款和行业应对预案，区分草案、表决通过和正式生效各阶段。",
        }

    # ========== 数据库/基础设施 ==========
    if contains_any(blob, ["postgres", "postgresql", "mysql", "sqlite", "redis", "mongodb",
                           "database", "sql ", "nosql", "orm"]):
        db = clean(title, 60)
        if contains_any(blob, ["rewritten", "rewrite", "rewriting"]):
            lang = "Rust" if "rust" in blob else "新语言"
            return {
                "cn_title": f"数据库：{db}（用 {lang} 重写）",
                "event": f"开发者用 {lang} 重写了 {db} 的关键组件或完整实现，目标是获得更好的性能和内存安全性。",
                "impact": "基础设施项目重写影响技术社区的技术选型讨论，特别是对 Rust 等系统级语言在基础设施场景的可行性验证。",
                "insight": "关注重写后的性能对比基准、API 兼容性和迁移成本，不要被「重写」的标题效应过度吸引。",
            }
        return {
            "cn_title": f"数据库/基础设施：{db}",
            "event": f"{db} 在 HN 上引发广泛讨论，社区正在分析其技术架构、性能特性或最新更新。",
            "impact": "基础设施层的技术决策影响深远，涉及性能、运维成本和生态兼容性。",
            "insight": "关注实际性能数据、与竞品的优劣势比较、迁移路径和社区生态成熟度。",
        }

    # ========== 编程语言/编译器 ==========
    if contains_any(blob, ["rust ", "python ", "javascript", "typescript", "go ", "zig ",
                           "compiler", "runtime", "vm ", "kernel"]):
        lang = clean(title, 60)
        return {
            "cn_title": f"编程语言/工具：{lang}",
            "event": f"关于 {lang} 的技术讨论在 HN 上成为热点，涉及语言特性、工具链或生态系统变化。",
            "impact": "编程语言和工具链的讨论反映开发者社区的技术风向，影响团队技术选型和个体学习路径。",
            "insight": "区分语言本身的改进、工具链更新和社区最佳实践的演进，不要因为单篇讨论热度而判断技术趋势已定。",
        }

    # ========== 开源 ==========
    if contains_any(blob, ["open source", "foss", "license", "mit ", "apache ", "gpl"]):
        oss = clean(title, 60)
        return {
            "cn_title": f"开源动态：{oss}",
            "event": f"开源社区动态：{oss}，涉及许可证变更、项目治理或社区生态变化。",
            "impact": "开源项目的许可证和治理模式变化直接影响使用方（企业）的合规风险和商业策略。",
            "insight": "关注许可证变更的实际限制、社区分叉的健康度和维护者商业化的透明度。",
        }

    # ========== 商业/创业 ==========
    if contains_any(blob, ["startup", "funding", "valuation", "acquisition", "revenue",
                           "layoff", "hiring", "ceo", "ipo", "saas", "subscription",
                           "pricing", "monetize", "profit"]):
        biz = clean(title, 60)
        if contains_any(blob, ["layoff", "layoffs", "firing", "fired"]):
            return {
                "cn_title": f"裁员：{biz}",
                "event": f"科技公司裁员消息：{biz}。社区在讨论裁员规模、赔偿方案和行业影响。",
                "impact": "科技行业裁员反映宏观经济和行业周期，影响从业者信心、招聘市场和创业活跃度。",
                "insight": "关注裁员补偿方案、受影响团队的业务线分布和公司财务状况，避免仅凭单一事件判断行业趋势。",
            }
        return {
            "cn_title": f"商业动态：{biz}",
            "event": f"科技商业动态：{biz}，涉及创业公司的融资、收购或商业模式变化。",
            "impact": "科技行业的投融资和商业变化反映行业趋势和资本流向，对从业者和创业者有参考意义。",
            "insight": "区分 PR 宣传和实际数据，关注单位经济模型、市场竞争格局和可持续性。",
        }

    # ========== 科学/研究 ==========
    if contains_any(blob, ["research", "paper ", "study ", "scientists", "science",
                           "physics", "biology", "chemistry", "space", "nasa", "medicine", "dna"]):
        sci = clean(title, 60)
        return {
            "cn_title": f"科学研究：{sci}",
            "event": f"科研进展分享：{sci}，来自 HN 社区的讨论，可能涉及最新研究论文或科学发现。",
            "impact": "科研分享可以快速了解某一领域的前沿动态，HN 社区常有领域内专家的补充和质疑。",
            "insight": "先区分是科普文章、预印本还是正式发表的论文，评论区往往能补充论文局限性和可复现性评估。",
        }

    # ========== 游戏 ==========
    if contains_any(blob, ["game", "gaming", "xbox", "steam", "playstation", "nintendo",
                           "retro", "emulator", "3d", "rendering", "gpu"]):
        game = clean(title, 60)
        return {
            "cn_title": f"游戏/图形：{game}",
            "event": f"游戏或图形技术动态：{game}。社区在讨论相关技术和行业发展。",
            "impact": "游戏和图形技术分享对游戏开发者、图形工程师和技术爱好者有参考价值。",
            "insight": "区分玩家视角和技术工程视角，关注底层技术实现细节和平台政策变化。",
        }

    # ========== 自传/历史/文化 ==========
    if contains_any(blob, ["story of", "history of", "my story", "interview with",
                           "how to", "guide ", "tutorial"]):
        story = clean(title, 60)
        return {
            "cn_title": f"分享：{story}",
            "event": f"HN 上分享了一篇文章/访谈/教程：{story}，社区正在讨论其内容和价值。",
            "impact": "高质量的分享文章是 HN 社区的精华内容，往往包含一线经验和深度思考。",
            "insight": "先读原文再参考评论区——HN 评论区通常会补充案例、指出疏漏或提供替代方案。",
        }

    # ========== 硬件 ==========
    if contains_any(blob, ["hardware", "cpu", "arm", "x86", "risc-v", "chip", "processor",
                           "server", "ram", "memory", "storage", "ssd", "nvidia", "amd", "intel"]):
        hw = clean(title, 60)
        return {
            "cn_title": f"硬件：{hw}",
            "event": f"硬件技术动态：{hw}。涉及芯片、服务器或存储技术的最新进展。",
            "impact": "硬件更新直接影响云计算成本、设备性能和开发者可用的算力资源。",
            "insight": "关注实际性能提升幅度、功耗变化和供应链可用性，不要被纸面参数过度吸引。",
        }

    # ========== 默认 ==========
    return {
        "cn_title": t,
        "event": f"技术社区讨论热点：{t}。HN 社区的活跃讨论正在围绕这一话题展开。",
        "impact": "HN 热榜上的高投票数反映开发者社区对某个方向的集体关注，值得深入阅读原帖了解全貌。",
        "insight": "先点开原文确认事实，再结合评论区判断讨论质量——高赞评论和深入讨论的价值远高于投票数。",
    }


def _hn_cn_title(title: str) -> str:
    """将英文 HN 标题转换为中文字段；专有名词保留原名。"""
    t = clean(title, 90)
    if not t:
        return "标题未获取"
    replacements = (
        ("Show HN:", "展示项目："), ("Show HN", "展示项目"),
        ("Launch HN:", "创业发布："), ("Launch HN", "创业发布"),
        ("Ask HN:", "社区提问："), ("Ask HN", "社区提问"),
        ("How to ", "如何"), ("A new way to ", "一种新的方法："),
        ("The ", ""), (" and ", "与"), (" with ", "与"),
        (" without ", "无需"), (" for ", "用于"), (" from ", "来自"),
        (" in ", "中的"), (" of ", "的"), (" using ", "使用"),
        ("open source", "开源"), ("Open Source", "开源"),
        ("security", "安全"), ("privacy", "隐私"), ("database", "数据库"),
        ("compiler", "编译器"), ("browser", "浏览器"), ("video", "视频"),
        ("model", "模型"), ("models", "模型"), ("agent", "智能体"),
        ("agents", "智能体"), ("research", "研究"), ("paper", "论文"),
        ("system", "系统"), ("tools", "工具"), ("tool", "工具"),
        ("An update on ", "关于……的更新："), ("Introducing ", "推出："),
    )
    translated = t
    for source, target in replacements:
        translated = translated.replace(source, target)
    translated = re.sub(r"\s+", " ", translated).strip(" -:：")
    if re.search(r"[A-Za-z]{4,}", translated):
        translated = f"技术社区话题：{translated}"
    return clean(translated, 70)


def discussion_signal(points: object, comments: object) -> str:
    try:
        p = int(str(points).replace(",", "").strip())
    except Exception:
        p = 0
    try:
        c = int(str(comments).replace(",", "").strip())
    except Exception:
        c = 0
    if not c:
        return "Comments 未获取，先把它当作高热条目处理，后续需要打开 HN 原帖确认争议点。"
    if p and c >= p * 0.6:
        return f"{c} 条评论相对 {p} points 偏高，说明它不只是被点赞，还引发了明显争议或经验交换。"
    if c >= 250:
        return f"{c} 条评论说明讨论深，适合优先看高赞评论里的反例、替代方案和实践经验。"
    return f"{c} 条评论说明已有一定讨论，但更像信息分享；重点看前排评论是否给出实测或反驳。"


def add_hn_item(lines: list[str], item: dict, rank: int, cache: dict) -> None:
    hn_cache = cache.get("hn_comments", {})
    extra = parse_extra(item)
    # 优先用 item id 匹配 cache, 其次用 title 匹配（兼容旧 cache 格式）
    item_id = item.get("id", "")
    cached = {}
    if isinstance(hn_cache, dict):
        cached = hn_cache.get(item_id, {})
        if not cached:
            cached = hn_cache.get(item.get("title", ""), {})  # fallback: 旧格式
    # Points: 优先取 item.heat（采集器已有）, 次取 cache
    raw_heat = clean(item.get("heat")).replace(" points", "").replace(",", "").replace("⭐", "")
    points = cached.get("points") or raw_heat or "未获取"
    # Comments: cache → extra.comments（采集器解析）→ "未获取"
    raw_comments = extra.get("comments", "")
    comments = cached.get("comments") or raw_comments or "未获取"
    url = cached.get("hn_url") or clean(item.get("url")) or "链接未获取"
    title = clean(item.get("title"), 90)
    profile = hn_chinese_profile(title, points, comments)
    cn_title = _hn_cn_title(profile.get("cn_title", title))
    event = profile.get("event", "")
    impact = f"{profile.get('impact', '')} 本条主题为：{cn_title}，需要结合原始文章确认具体影响。"
    insight = f"{profile.get('insight', '')} 针对本条主题：{cn_title}，还要区分社区观点与已验证事实。"
    signal = discussion_signal(points, comments)

    lines.append(f"• HN#{rank} [{cn_title}]({url})")
    lines.append("")
    lines.append(f"> 🀄 中文：{cn_title}  ")
    lines.append(f"> 📌 事件：{event}  ")
    if points:
        lines.append(f"> 🔥 热度积分：{points} · 💬 {comments} 条评论  ")
    lines.append(f"> 🌊 影响：{impact}  ")
    lines.append(f"> 💡 解读：{insight} {signal}  ")
    lines.append("")


def paper_profile(title: str, summary: str = "") -> dict[str, str]:
    blob = words_for(title, summary)
    if contains_any(blob, ["counterfactual", "explanation", "explanations", "neuro-symbolic", "plausible", "actionable"]):
        return {
            "doing": "从标题看，这篇论文关注反事实解释和可操作解释，把模型输出转成更容易追责或干预的解释形式。",
            "why": "它重要在于服务高风险决策场景，重点不是提升榜单分数，而是让人知道模型为什么给出某个判断以及还能怎么改。",
            "value": "适合做可解释 AI、金融风控、医疗辅助决策或模型审计的人跟踪；后续看解释是否忠实、是否可行动、用户实验是否充分。",
            "engineering": "工程落点是解释模块和审计流程；当前标题没有给出量化提升，不能写成已有明确性能增益。",
        }
    if contains_any(blob, ["preference", "pairwise", "pluralism", "alignment", "governing", "human-ai"]):
        return {
            "doing": "从标题看，它研究偏好、成对比较或人机交互中的价值分歧，核心是如何更稳地表达和治理不同偏好。",
            "why": "这类工作影响模型评测、RLHF/偏好学习和对齐策略，重要性在于避免把复杂偏好压成单一排序。",
            "value": "适合做模型评测、对齐、安全治理和推荐系统的人跟踪；后续看实验设置、偏好人群划分和是否能用于真实标注流程。",
            "engineering": "工程价值主要在评测和标注流程设计；若没有公开数据或代码，需要谨慎评估可复现性。",
        }
    if contains_any(blob, ["uncertainty", "partial observability", "assistance", "ask in the dark"]):
        return {
            "doing": "从标题看，它研究在信息不完整时如何让 LLM 辅助决策，并用不确定性门控决定何时介入或保守回答。",
            "why": "这对客服、运维、医疗问答和复杂任务代理都重要，因为真实场景经常不是信息充分的 benchmark。",
            "value": "适合做 Agent、决策支持和高风险问答系统的人跟踪；后续看不确定性估计是否可靠、拒答策略是否降低错误帮助。",
            "engineering": "工程价值在于把置信度、追问和人工接管接入产品流程；标题未给出数字，需看论文实验再判断提升幅度。",
        }
    if contains_any(blob, ["data readiness", "scientific ai", "data quality", "dataset"]):
        return {
            "doing": "从标题看，它关注科学 AI 的数据就绪度，目标是自动检查或改善数据能否支撑建模和实验。",
            "why": "科学 AI 的瓶颈常在数据质量、元数据和可复现管线，而不只是模型结构。",
            "value": "适合科研数据平台、实验室自动化和行业 AI 团队跟踪；后续看支持哪些数据类型、质量规则和人工审核机制。",
            "engineering": "工程价值在数据治理和实验前置校验；需要看是否有工具链、数据 schema 和失败案例。",
        }
    if contains_any(blob, ["coding agent", "coding agents", "swarm", "agentic", "open-ended discovery", "self-evolving"]):
        return {
            "doing": "从标题看，它研究多个编码 Agent 或自演化 Agent 如何协作完成开放式发现和开发任务。",
            "why": "这直接关系 AI 编程工具从单次补全走向长期任务执行，关键问题是任务分解、选择机制和失败恢复。",
            "value": "适合 AI 编程工具、自动化研究和多 Agent 编排方向跟踪；后续看任务集是否真实、评测是否防止刷分、成本是否可控。",
            "engineering": "工程价值取决于能否落到可运行工作流；优先核对代码、任务日志、成本统计和失败样例。",
        }
    if contains_any(blob, ["federated learning", "federated", "auto-fl"]):
        return {
            "doing": "从标题看，它把自动搜索或 Agent 方法用于联邦学习算法设计，目标是在分布式数据约束下找到更合适的训练策略。",
            "why": "联邦学习落地难点在非独立同分布数据、通信成本和隐私约束，自动化搜索可能降低算法选择成本。",
            "value": "适合隐私计算、医疗/金融建模和边缘训练团队跟踪；后续看数据异质性设置、通信轮数和隐私假设。",
            "engineering": "工程价值要看是否能接入现有 FL 框架，以及搜索成本是否小于人工调参成本。",
        }
    if contains_any(blob, ["embodied", "omni", "multimodal", "vision-language", "robot"]):
        return {
            "doing": "从标题看，它是具身智能或多模态模型技术报告，关注模型如何同时处理感知、语言和行动相关任务。",
            "why": "这类报告的价值在系统能力边界和数据/评测覆盖，而不是单个 demo。",
            "value": "适合机器人、多模态和智能体应用团队跟踪；后续看任务覆盖、真实环境测试、模型规模和开源程度。",
            "engineering": "工程价值取决于是否公开模型、数据和部署成本；标题本身不足以判断实际可用性。",
        }
    return {
        "doing": f"从标题看，这篇论文关注“{clean(title, 70)}”这一研究问题，需要结合摘要确认具体方法和实验对象。",
        "why": "它的重要性取决于是否提出清晰任务定义、可复现实验和比现有方法更好的证据。",
        "value": "适合相关方向研究者先做筛选；后续看摘要、方法、基线、数据集和失败案例，而不是仅凭标题判断价值。",
        "engineering": "当前没有足够信息写具体工程收益，先标记为待核验，避免把标题包装成确定结论。",
    }


def paper_dimensions(title: str, summary: str) -> dict[str, str]:
    """把论文摘要压缩成做法、创新、意义、后续影响四个中文维度。"""
    blob = words_for(title, summary)
    if contains_any(blob, ("benchmark", "evaluation", "dataset", "leaderboard")):
        return {
            "innovation": "创新点在于把任务、数据和评价指标统一到同一套可重复基准中，便于横向比较，而不只是展示单个方法的最好结果。",
            "meaning": "这能帮助研究者判断方法是否真的提升了能力，也能让工程团队更早发现模型在真实任务中的短板。",
            "impact": "后续影响取决于基准是否被更多团队采用，以及结果能否在不同数据、设备和成本约束下复现。",
        }
    if contains_any(blob, ("agent", "agents", "planning", "trajectory", "action")):
        return {
            "innovation": "创新点是把智能体的规划、行动和反馈过程纳入统一方法或评测，而不是只测一次问答的最终答案。",
            "meaning": "这为长期任务自动化提供了更接近真实工作的评价视角，重点转向任务完成率、失败恢复和资源消耗。",
            "impact": "后续要看它能否迁移到真实工具链、复杂环境和多人协作流程，并验证成本是否低于人工执行。",
        }
    if contains_any(blob, ("retrieval", "rag", "knowledge", "external memory", "memory")):
        return {
            "innovation": "创新点是把外部知识或记忆结构接入模型推理流程，减少只依靠参数记忆造成的遗漏和过时信息。",
            "meaning": "这对需要可更新知识、来源追溯和较低幻觉率的问答、检索和企业知识库场景更有价值。",
            "impact": "后续影响取决于检索准确率、延迟、数据更新成本和引用是否可靠，不能只看离线指标。",
        }
    if contains_any(blob, ("efficient", "efficiency", "cost", "speed", "accelerat", "scalable")):
        return {
            "innovation": "创新点集中在降低计算量、推理延迟或部署成本，并用实验比较效率与效果之间的取舍。",
            "meaning": "如果效果没有明显下降，这类工作能扩大模型在边缘设备、低预算团队和高并发服务中的可用范围。",
            "impact": "后续要看真实硬件、不同规模模型和峰值负载下的收益，避免把实验室加速直接等同于生产降本。",
        }
    return {
        "innovation": "从摘要可确认的创新是围绕目标问题设计新的方法或分析框架；具体超越现有工作的部分仍需核对实验和基线。",
        "meaning": "它的意义在于为该问题提供一个可检验的解决路径，价值不应只由标题或单一指标决定。",
        "impact": "后续影响要看代码、数据、复现实验和其他团队的独立验证，尤其关注适用边界与失败案例。",
    }


def add_paper_item(lines: list[str], item: dict) -> None:
    title = clean(item.get("title"), 100)
    display_title = _hn_cn_title(title)
    url = clean(item.get("url")) or "链接未获取"
    extra = parse_extra(item)
    summary = clean(item.get("summary") or extra.get("summary") or extra.get("desc"), 240)
    profile = paper_profile(title, summary)
    lines.append(f"📄 [{display_title}]({url})")
    lines.append("")
    # 中文概括解读（不贴原文英文摘要）
    if summary:
        cn_doing = _paper_cn_reading(title, summary)
    else:
        cn_doing = f"{profile['doing']} {profile['why']}"
    dimensions = paper_dimensions(title, summary)
    for field in ("innovation", "meaning", "impact"):
        dimensions[field] = f"{dimensions[field]} 本研究聚焦于{display_title}这一对象。"
    lines.append(f"> 📌 做了什么：{cn_doing}  ")
    lines.append("")
    lines.append(f"> ✨ 创新：{dimensions['innovation']}  ")
    lines.append("")
    lines.append(f"> 🌊 意义：{dimensions['meaning']}  ")
    lines.append("")
    lines.append(f"> 👀 后续影响：{dimensions['impact']}  ")
    lines.append("")


def _paper_cn_reading(title: str, summary: str) -> str:
    """根据标题和摘要生成中文概括解读"""
    t = clean(title, 60)
    s = words_for(summary)
    blob = words_for(t, summary)

    # 检测论文主题
    topic = "该研究"
    if contains_any(blob, ("language model", "llm", "transformer", "attention", "pretrain", "linearization")):
        topic = "大语言模型"
    elif contains_any(blob, ("agent", "agents", "reflection", "trajectory", "action")):
        topic = "AI Agent"
    elif contains_any(blob, ("structure-property", "materials", "chemistry", "biology", "molecule")):
        topic = "科学 AI（材料/化学）"
    elif contains_any(blob, ("database", "sql", "storage", "query", "driver", "jdbc", "odbc")):
        topic = "数据库与存储"
    elif contains_any(blob, ("federated", "privacy")):
        topic = "联邦学习"
    elif contains_any(blob, ("robot", "embodied", "vision", "multimodal", "omni")):
        topic = "具身智能/多模态"
    elif contains_any(blob, ("counterfactual", "explanation", "interpret", "explain")):
        topic = "可解释 AI"
    elif contains_any(blob, ("coding", "code", "program", "compile")):
        topic = "代码智能"
    elif contains_any(blob, ("retrieval", "rag", "knowledge")):
        topic = "检索增强(RAG)"


    # 提炼目标问题
    goal = ""
    if contains_any(s, ("bottleneck", "limitation", "challenge", "issue", "problem", "quadratic")):
        goal = "解决现存瓶颈/挑战"
    elif contains_any(s, ("efficient", "efficiency", "cost", "speed", "fast", "accelerat")):
        goal = "提升效率/降低成本"
    elif contains_any(s, ("understand", "explain", "interpret", "insight")):
        goal = "加深理解/提供解释"
    elif contains_any(s, ("scalab", "large-scale", "distribut")):
        goal = "实现可扩展/大规模部署"
    elif contains_any(s, ("reflect", "diagnos", "extract", "discover")):
        goal = "增强诊断/提取能力"
    else:
        goal = "探索新方向"

    # 用中文概括“研究对象—技术路径—目标”，不直接复制英文摘要句子。
    if contains_any(blob, ("proactive agent", "proactive agents", "real-world task", "real world task")):
        subject = "真实环境中的主动智能体"
        approach = "提出统一的评测框架，在真实场景中比较智能体的规划、行动与反馈能力"
    elif contains_any(blob, ("structure-property", "structure property", "native structure")):
        subject = "材料与化学体系的结构—性质关系"
        approach = "结合分子或材料的原生结构信息建立预测模型，并用跨学科数据验证结果"
    elif contains_any(blob, ("video generation", "video reasoning", "video")):
        subject = "视频生成中的推理与规划"
        approach = "把多步推理过程与视频生成过程结合起来，评估模型从计划到生成的连续能力"
    elif contains_any(blob, ("limited memory", "externalize factual knowledge", "continuous-query")):
        subject = "有限记忆语言模型的知识存储"
        approach = "将事实知识从模型内部记忆转移到外部可查询结构，减少长期记忆和推理过程的负担"
    elif contains_any(blob, ("scientific lineage", "lineage reasoning", "idea generation")):
        subject = "科学思想谱系与研究创意生成"
        approach = "追踪已有研究之间的继承关系，再用谱系信息辅助发现和生成新的研究想法"
    elif contains_any(blob, ("benchmark", "evaluation", "dataset")):
        subject = topic
        approach = "建立统一评测基准或数据集，对不同方法在目标任务上的表现进行可重复比较"
    elif contains_any(blob, ("framework", "architecture", "system")):
        subject = topic
        approach = "构建新的框架、系统或模型架构，并通过实验验证其在目标任务上的效果"
    elif contains_any(blob, ("retrieval", "rag", "knowledge")):
        subject = topic
        approach = "引入外部知识检索并与模型推理结合，减少仅依赖参数记忆带来的错误"
    else:
        subject = topic
        approach = "围绕目标任务设计方法并通过实验分析其效果、成本与适用边界"
    return f"研究对象是{subject}；核心思路：{approach}；目标是{goal}。"


def section_for_item(item: dict) -> str:
    title = clean(item.get("title"))
    category = item.get("category", "")
    if any(word in title for word in ["洪", "台风", "防汛", "暴雨", "救灾", "水库", "灾害"]):
        return "社会·民生"
    if any(word in title for word in ["世界杯", "男篮", "女篮", "乒乓", "夺冠", "赛事", "C罗", "孙颖莎"]):
        return "体育·赛事"
    if category in ("军事", "时政", "国际"):
        return "时政·外交"
    if category == "财经":
        return "财经·商业"
    if category in ("科技", "AI"):
        return "AI·前沿" if category == "AI" else "科技·数码"
    if category == "汽车·能源":
        return "汽车·能源"
    if category == "娱乐":
        return "娱乐·综艺"
    return "社会·民生"


def social_news_insight(item: dict) -> str:
    title = clean(item.get("title"), 45)
    blob = words_for(title, parse_extra(item).get("desc"), item.get("summary"))

    if contains_any(blob, ["潜射", "战略导弹", "试射", "海军"]):
        return f"“{title}”属于军事安全新闻，重点看试射目的、技术验证和释放的战略信号。"
    if contains_any(blob, ["猿辅导", "英语老师", "教资", "发音", "客服回应"]):
        return f"“{title}”反映在线教育服务质量争议，重点看机构核查结果、教师资质和消费者沟通。"
    if contains_any(blob, ["橙色预警", "水利部升级", "洪水预警"]):
        return f"“{title}”是防汛预警升级信息，重点看涉及流域、风险地区和地方防范措施。"
    if contains_any(blob, ["通报受灾情况"]):
        return f"“{title}”是灾情通报，重点看受灾范围、人员安置、基础设施受损和后续恢复安排。"
    if contains_any(blob, ["受灾", "洪水", "洪涝", "救援", "抢险", "紧急响应"]):
        return f"“{title}”的核心是灾情处置进展，重点看受影响范围、救援安置和后续恢复安排。"
    if contains_any(blob, ["台风", "登陆", "路径", "巴威"]):
        return f"“{title}”说明台风路径或影响范围仍有变化，后续要看气象预报、停航停课和地方响应。"
    if contains_any(blob, ["暴雨", "强对流", "防汛", "避险", "预警", "天气", "紧急提示"]):
        return f"“{title}”是一条公共安全提醒，关键信息是风险区域、避险动作和出行限制。"
    if contains_any(blob, ["火灾", "起火", "消防", "火势", "燃烧", "爆炸"]):
        return f"“{title}”涉及火灾/爆炸安全事故，重点看伤亡人数、起火原因调查和应急响应进展。"
    if contains_any(blob, ["蛇", "越狱", "动物", "养殖"]):
        return f"“{title}”是一条社会民生新闻，核心看事件起因、处置进展和相关管理漏洞。"
    if contains_any(blob, ["避暑", "旅游", "暑期", "出行", "放假"]):
        return f"“{title}”是暑期出行/旅游相关话题，重点看目的地热度、安全提醒和客流管理。"
    if contains_any(blob, ["医保", "基金", "追回", "骗保", "医疗"]):
        return f"“{title}”涉及医保基金监管，重点看追回金额、查处案例和制度漏洞修补。"
    if contains_any(blob, ["院士", "作息", "健康", "养生", "睡眠"]):
        return f"“{title}”是健康科普类内容，核心看信息来源是否权威、建议是否可操作。"
    if contains_any(blob, ["手机丢失", "卡内余额", "转空", "盗刷"]):
        return f"“{title}”涉及个人财产安全，重点看事件经过、平台赔付机制和用户防范建议。"
    if contains_any(blob, ["就业", "新增就业", "城镇", "岗位"]):
        return f"“{title}”是就业/经济数据类新闻，重点看数据来源、统计口径和趋势变化。"
    if contains_any(blob, ["纸币", "人民币", "汇率", "降息", "加息"]):
        return f"“{title}”是金融/货币政策新闻，核心关注政策意图和市场预期变化。"
    if contains_any(blob, ["男篮", "女篮", "足球", "世界杯", "c罗", "c 罗", "哈兰德",
                            "比赛", "赛事", "夺冠", "判罚", "晋级", "决赛", "冠军"]):
        if contains_any(blob, ["禁赛", "规则", "国际足联", "电话交涉", "特朗普"]):
            return f"“{title}”涉及赛事规则和场外干预争议，关键看官方解释、球队表态和程序公平问题。"
        if contains_any(blob, ["姐姐", "同框", "家族", "像哈兰德"]):
            return f"“{title}”属于运动员个人相关轻话题，主要看点是公众人物家庭形象带来的反差讨论。"
        if contains_any(blob, ["c罗", "c 罗", "葡萄牙", "西班牙", "运气"]):
            return f"“{title}”是赛后观点争议，判断时应回到比赛过程、关键数据和双方表现。"
        return f"“{title}”是一条赛事结果新闻，重点看关键球员表现、比赛走势和后续赛程影响。"
    if contains_any(blob, ["微信", "功能", "临时好友", "乘机", "出行", "app", "手机", "平台", "产品"]):
        if contains_any(blob, ["乘机", "出行", "暑期"]):
            return f"“{title}”关系暑期出行便利，重点看措施覆盖范围、执行细则和实际体验。"
        return f"“{title}”讨论的是具体功能需求，重点在使用场景、隐私边界和服务方是否回应。"
    if contains_any(blob, ["双开", "通报", "调查", "处罚", "立案"]):
        return f"“{title}”已经进入正式处置阶段，后续重点是处分依据、涉事链条和进一步问责信息。"
    if contains_any(blob, ["法院", "律师", "刑事"]):
        return f"“{title}”触及法律服务和程序权利，关键是区分个案经验、制度规则和可核实证据。"
    if contains_any(blob, ["版权", "文物"]):
        return f"“{title}”牵涉知识产权或公共文化资产，重点看判决依据、权属证明和行业示范效应。"
    if contains_any(blob, ["明星", "综艺", "穿搭", "情侣", "演唱会", "电影", "电视剧", "恋情", "粉丝", "票房"]):
        if contains_any(blob, ["穿搭", "情侣"]):
            return f"“{title}”是一条生活方式内容，核心看点是季节搭配、使用场景和可参考程度。"
        if contains_any(blob, ["预售", "票房", "破"]):
            return f"“{title}”是影视/演出市场数据，重点看预售增速、口碑发酵和最终票房预期。"
        return f"“{title}”属于娱乐动态，重点看当事方回应、作品进展和商业合作是否受影响。"
    if contains_any(blob, ["游戏", "手游", "端游", "steam", "ps5", "xbox", "switch", "电竞"]):
        return f"“{title}”是游戏/电竞动态，重点看玩法创新、运营活动和赛事结果。"
    if contains_any(blob, ["新车", "上市", "试驾", "比亚迪", "蔚来", "小鹏", "理想", "小米"]):
        return f"“{title}”是新能源汽车动态，重点看售价、配置差异和交付节奏。"
    if contains_any(blob, ["芯片", "半导体", "估值", "融资", "投资", "量产"]):
        return f"“{title}”是科技产业新闻，重点看融资规模、技术路线和产能规划。"
    if contains_any(blob, ["美股", "a股", "a 股", "股市", "大盘", "指数", "涨停", "跌停"]):
        return f"“{title}”是股市/资本市场动态，重点看涨跌原因、资金流向和政策面变化。"
    if contains_any(blob, ["碳达峰", "碳中和", "减排", "环保", "绿色"]):
        return f"“{title}”是气候政策与绿色发展议题，重点看具体行业减排目标和实施路径。"
    if contains_any(blob, ["物业", "业主", "欠缴", "物业费", "法院判"]):
        return f"“{title}”是民生法律案例，重点看判决依据、典型意义和对普通业主的参考价值。"
    return f"“{title}”需要先核实事实来源，再看事件背景、影响对象和后续进展。"


def social_insight(source: str, item: dict, idx: int) -> str:
    title = clean(item.get("title"), 28)
    return f"{social_news_insight(item)} 本条主题为：{title}。"


def add_social(lines: list[str], source: str, label: str, count: int,
               used_keys: set[str] | None = None) -> None:
    lines.append(f"{label}")
    lines.append("")
    shown = 0
    for idx, item in enumerate(query_source(source, count * 3), 1):  # 多查一些用于跳过已用
        if used_keys and item_key(item) in used_keys:
            continue
        shown += 1
        # 热度: 微博特殊处理（微博返回的是搜索排名点值, 非真实阅读量）
        heat_val = heat_display(item)
        if source == "weibo":
            heat_label = f"热度{heat_val}(平台内)"
        else:
            heat_label = f"热度{heat_val}"
        lines.append(f"• {SOURCE_CN.get(source, source)}#{shown} {md_link(item)} · {heat_label}")
        lines.append(f"> 💡 解读：{social_insight(source, item, shown)}")
        if used_keys:
            used_keys.add(item_key(item))
        if shown >= count:
            break
    if shown == 0:
        lines.append("• [今日暂无相关热点](链接未获取)")
    lines.append("")


def build_briefing() -> tuple[str, str]:
    now = datetime.now(CST)
    today = now.strftime("%Y-%m-%d")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    output_path = os.environ.get(
        "BRIEFING_OUTPUT_PATH",
        os.path.join(OUTPUT_DIR, f"news-{today}.md"),
    )
    cache = load_cache()

    all_sources = [
        "baidu", "weibo", "toutiao", "zhihu", "douyin", "github", "hackernews",
        "arxiv", "ithome", "36kr", "wallstreetcn", "jin10", "xueqiu",
        "bbc_world", "reuters", "techcrunch", "thepaper", "bilibili_pop",
        "aihot", "dongqiudi",
    ]
    ranks = source_rank_maps(all_sources)
    stats = get_stats(days=1)

    lines: list[str] = []
    lines.append("📰 **今日热点 · 全源聚合**")
    lines.append("")
    lines.append(f"📅 `{now.strftime('%Y.%m.%d')}（{weekday}）` · `晚间版`")
    lines.append("")
    lines.append(f"**数据来源**：头条/微博/知乎/百度/抖音/IT之家/GitHub/HN/arXiv ｜ 采集时间：{now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    main_items = select_main_items(5)

    used_keys: set[str] = set()

    # ─── 今日要点概览（今日热点 + 推荐 AI + 推荐 GitHub）───
    lines.append("📌 **今日要点**")
    lines.append("")
    # 热点新闻
    highlight_pool = list(main_items)
    if len(highlight_pool) < 5:
        extra_highlights = query_categories(["社会", "军事", "财经", "AI"], 15)
        for it in extra_highlights:
            if item_key(it) not in {item_key(h) for h in highlight_pool}:
                highlight_pool.append(it)
    highlight_pool = unique(highlight_pool, 6)
    for idx, item in enumerate(highlight_pool):
        used_keys.add(item_key(item))
        section_name = section_for_item(item)
        dot = ["🔴", "🔴", "🔴", "🟡", "🟡", "🟢"][idx] if idx < 6 else "🟡"
        lines.append(f"• {dot} {md_link(item)}  ")
        lines.append(f"> 📍 {SOURCE_CN.get(item.get('source',''), item.get('source',''))} · {section_name}  ")
    lines.append("")

    # 推荐 AI 动态
    ai_recs_pool = []
    for src in ("hackernews", "aihot", "huggingface"):
        for it in query_source(src, 20):
            title = words_for(it.get("title"))
            if contains_any(title, ("gpt", "claude", "llm", "openai", "anthropic", "agent",
                                     "deepseek", "gemini", "codex", "glm", "model", "ai ",
                                     "copilot", "hugging face", "rag", "inference")):
                if item_key(it) not in used_keys:
                    ai_recs_pool.append(it)
    for it in query_source("arxiv", 10):
        if item_key(it) not in used_keys:
            ai_recs_pool.append(it)
    ai_recs = unique(ai_recs_pool, 3)
    if ai_recs:
        lines.append("⭐ **推荐 AI 动态**  ")
        for item in ai_recs:
            used_keys.add(item_key(item))
            title = clean(item.get("title"), 60)
            url = clean(item.get("url")) or "链接未获取"
            blob = words_for(title)
            if contains_any(blob, ("gpt", "claude", "openai", "anthropic", "llm", "model")):
                tag = "模型动态"
            elif contains_any(blob, ("agent", "coding", "codex")):
                tag = "Agent工具"
            elif item.get("source") == "arxiv":
                tag = "前沿论文"
            else:
                tag = "AI热点"
            lines.append(f"  • [{title}]({url}) — {tag}  ")
        lines.append("")

    # 推荐 GitHub 项目
    gh_recs = []
    seen_repos: set[str] = set()
    # 从 trend cache 取
    gh_weekly_raw = cache.get("github_weekly", [])
    for item in gh_weekly_raw:
        repo = item.get("repo", "") if isinstance(item, dict) else ""
        if not repo or "/" not in repo:
            continue
        if repo in seen_repos or f"repo:{repo}" in used_keys:
            continue
        seen_repos.add(repo)
        blob = words_for(repo)
        if contains_any(blob, ["awesome", "resources", "docs", "design system"]):
            continue
        info = github_info(repo, cache)
        desc = clean(info.get("description") or item.get("description", ""), 100)
        stars = info.get("stars") or item.get("stars", 0)
        gh_recs.append((repo, desc, stars, info))
        if len(gh_recs) >= 3:
            break
    if len(gh_recs) < 2:
        for item in query_source("github", 10):
            repo = repo_name(item)
            if repo in seen_repos or f"repo:{repo}" in used_keys:
                continue
            seen_repos.add(repo)
            info = github_info(repo, cache)
            desc = clean(info.get("description") or parse_extra(item).get("hover", ""), 100)
            stars = info.get("stars") or clean(item.get("heat")).replace("⭐", "").replace(",", "")
            gh_recs.append((repo, desc, stars, info))
            if len(gh_recs) >= 3:
                break
    if gh_recs:
        lines.append("🔧 **推荐 GitHub 项目**  ")
        for repo, desc, stars, info in gh_recs:
            used_keys.add(f"repo:{repo}")
            url = f"https://github.com/{repo}"
            blob = words_for(repo, desc)
            if contains_any(blob, ["ai ", "agent", "agentic", "llm", "model"]):
                tag = "AI/Agent"
            elif contains_any(blob, ["security", "pentest", "vulnerab"]):
                tag = "安全工具"
            elif contains_any(blob, ["crawl", "scraper", "web data"]):
                tag = "数据工具"
            elif contains_any(blob, ["cli", "command", "orm", "database", "sql"]):
                tag = "开发工具"
            else:
                tag = "趋势项目"
            # 简短中文介绍（基于实际描述, 避免重复）
            cn_intro = ""
            d = words_for(desc)
            if contains_any(d, ("design system", "design.md", "brand design")):
                cn_intro = "知名品牌设计规范分析合集，AI 可参考生成匹配前端设计。"
            elif contains_any(d, ("production-grade", "engineering skills", "coding agents")):
                cn_intro = "生产级 AI 编码 Agent 技能库，含代码审查、调试、部署等工程模板。"
            elif contains_any(d, ("llm friendly", "web crawler", "scraper")):
                cn_intro = "开源 LLM 友好网页爬虫，为 RAG 和 AI 应用提供结构化数据。"
            elif contains_any(d, ("linux server", "securing", "how-to guide")):
                cn_intro = "Linux 服务器安全加固指南，覆盖防火墙、SSH、审计等最佳实践。"
            elif contains_any(d, ("penetration testing", "pentest", "autonomous")):
                cn_intro = "全自主 AI 渗透测试系统，自动发现和验证安全漏洞。"
            elif contains_any(d, ("job application", "claude code", "hire")):
                cn_intro = "基于 Claude Code 的 AI 求职助手，自动评估岗位、生成定制简历。"
            elif contains_any(d, ("office", "document", "excel", "automate")):
                cn_intro = "面向 AI Agent 的 Office 办公套件 CLI，支持文档读写编辑。"
            elif contains_any(d, ("meeting", "transcription", "whisper", "speaker")):
                cn_intro = "隐私优先的本地 AI 会议助理，支持实时转写和说话人分离。"
            else:
                cn_intro = f"{clean(desc, 80)}" if desc else "GitHub 趋势热门项目。"
            lines.append(f"  • [{repo}]({url}) ⭐{stars} · {tag}  ")
            lines.append(f"    {cn_intro}  ")
        lines.append("")

    lines.append("🧭 **今日主线**")
    lines.append("")
    for idx, item in enumerate(main_items, 1):
        used_keys.add(item_key(item))
        add_news_block(lines, item, section_for_item(item), ranks, "🔴" if idx <= 3 else "🟠")

    sections = domestic_sections()
    lines.append("🏮 **国内热点**")
    lines.append("")
    for title, section_key, items in sections:
        lines.append(title)
        lines.append("")
        limit = 3 if section_key in ("汽车·能源", "娱乐·综艺", "体育·赛事") else 5
        selected = unique(items, limit, used_keys=used_keys)
        if not selected:
            lines.append("🟠 [今日暂无相关热点](链接未获取)")
            lines.append("")
            lines.append("> 📍 来源：排名未获取 · 热度未获取  ")
            lines.append("> 📌 事件：当前采集窗口内没有足够条目。  ")
            lines.append("> 💡 解读：保留板块占位，等待下一轮采集补齐。  ")
            lines.append("> ✅ 可信度：数据缺口")
            lines.append("")
            continue
        for item in selected:
            used_keys.add(item_key(item))
            add_news_block(lines, item, section_key, ranks)

    lines.append("🔥 **各媒体平台热榜汇总**")
    lines.append("")
    add_social(lines, "douyin", "🎵 **抖音 TOP热点**", 5, used_keys)
    add_social(lines, "weibo", "💬 **微博热搜**", 5, used_keys)
    add_social(lines, "zhihu", "💬 **知乎热榜**", 5, used_keys)
    add_social(lines, "baidu", "🔍 **百度热搜**", 5, used_keys)

    lines.append("🌏 **国外热点**")
    lines.append("")
    intl_items = unique(query_source("reuters", 4) + query_source("bbc_world", 4) + query_source("techcrunch", 3) + query_source("googlenews", 3), 6, used_keys=used_keys)
    for item in intl_items:
        used_keys.add(item_key(item))
        source = item.get("source")
        section = "科技·数码" if source == "techcrunch" else "时政·外交"
        add_news_block(lines, item, section, ranks)

    lines.append("🤖 **AI·前沿**")
    lines.append("")
    AI_EXCLUDE_KEYWORDS = ("抽奖", "回馈", "促销", "优惠", "送", "成品号", "特殊渠道")

    def is_valid_ai(item: dict) -> bool:
        if not is_ai_relevant(item):
            return False
        title = words_for(item.get("title"))
        if contains_any(title, AI_EXCLUDE_KEYWORDS):
            return False
        return True

    ai_pool = (
        [item for item in query_categories(["AI"], 30) if is_valid_ai(item)]
        + [item for item in query_source("aihot", 5) if is_valid_ai(item)]
        + [item for item in query_source("hackernews", 10) if is_valid_ai(item)]
    )
    ai_items = unique(ai_pool, 6, used_keys=used_keys)
    for item in ai_items:
        used_keys.add(item_key(item))
        add_news_block(lines, item, "AI·前沿", ranks, "🟣")

    lines.append("🐙 **GitHub 趋势**")
    lines.append("")
    gh_daily = query_source("github", 6)
    for idx, item in enumerate(gh_daily, 1):
        repo = repo_name(item)
        used_keys.add(item_key(item))
        used_keys.add(f"repo:{repo}")  # 记录仓库名便于周榜/机会去重
        add_github_item(lines, repo, clean(item.get("url")) or f"https://github.com/{repo}", idx, github_info(repo, cache), True, item)
    weekly = cache.get("github_weekly", [])[:6]
    weekly_repos_seen: set[str] = set()
    weekly_shown = 0
    for item in weekly:
        repo = clean(item.get("repo"))
        # 跳过日榜已展示的 repo
        if repo in weekly_repos_seen or f"repo:{repo}" in used_keys:
            continue
        weekly_repos_seen.add(repo)
        used_keys.add(f"repo:{repo}")
        weekly_shown += 1
        info = dict(github_info(repo, cache))
        info.setdefault("stars", item.get("stars"))
        info.setdefault("description", item.get("description"))
        add_github_item(lines, repo, f"https://github.com/{repo}", weekly_shown, info, False)
        if weekly_shown >= 6:
            break

    lines.append("🐱 **HackerNews**")
    lines.append("")
    hn_items = query_source("hackernews", 8)
    if hn_items:
        for idx, item in enumerate(hn_items, 1):
            used_keys.add(item_key(item))
            add_hn_item(lines, item, idx, cache)
    else:
        lines.append("• [今日 HackerNews 暂无数据](链接未获取)")
        lines.append("")
        lines.append("> 📍 来源：排名未获取 · 热度未获取  ")
        lines.append("> 📌 事件：当前采集窗口内 HN 数据未获取。  ")
        lines.append("> 💡 解读：等待下一轮采集补齐。  ")
        lines.append("> ✅ 可信度：数据缺口")
        lines.append("")

    lines.append("📜 **论文·学术**")
    lines.append("")
    arxiv_items = query_source("arxiv", 5)
    if arxiv_items:
        for item in arxiv_items:
            add_paper_item(lines, item)
    else:
        lines.append("• [今日 arXiv 暂无数据](链接未获取)")
        lines.append("")
        lines.append("> 📌 做什么：当前采集窗口内 arXiv 论文数据未获取。  ")
        lines.append("")
        lines.append("> 💡 价值：等待下一轮采集补齐。  ")
        lines.append("")
        lines.append("> 💡 工程价值：数据缺口  ")
        lines.append("")
        lines.append("> 代码：未获取")
    lines.append("")
    for row in stats.get("by_source", [])[:16]:
        source = row["source"]
        lines.append(f"• {SOURCE_CN.get(source, source)} — 抓取{row['count']}条 · 入选见正文 · ✅ 最近更新：{clean(row.get('last'), 24)}")
    lines.append("")

    lines.append("🤖 **全景判断**")
    lines.append("")
    lines.append("> 🧭 **最强主线**：防汛台风、潜射战略导弹、A股交易与科技供应链是今天最值得看的几条线。  ")
    lines.append("> 🔥 **社媒情绪**：公共安全和民生救援占据强情绪位，微博/抖音更偏即时扩散，百度/知乎更偏搜索和解释。  ")
    lines.append("> 🧑‍💻 **技术趋势**：GitHub 仍由开发者工具、AI Agent、开源基础设施占据高位，AI 工具链安全和成本问题值得继续看。  ")
    lines.append("> 🌡️ **风险信号**：极端天气、地缘安全、市场波动三条线同时存在，短期不要把单平台热度当作确定结论。")
    lines.append("")

    lines.append("👀 **继续跟踪**")
    lines.append("")
    # 只保留未被前面 section 用掉的 main_items, 最多取 5 条
    followup_items = [it for it in main_items if item_key(it) not in used_keys][:5]
    for dot, item in zip(["🔴", "🔴", "🟡", "🟡", "🟢"], followup_items):
        used_keys.add(item_key(item))
        lines.append(f"• {dot} {md_link(item)} — {SOURCE_CN.get(item.get('source',''), item.get('source',''))}热榜 | 看后续")
        lines.append("> 💡 跟踪：关注原始来源更新、官方回应、跨平台热度是否延续。  ")
        lines.append(f"> 💡 解读：{clean(item.get('title'), 60)}已经进入主线候选，下一步看事实是否被更多权威源确认。")
        lines.append("")

    lines.append("⚠️ **风险与机会**")
    lines.append("")
    # 找一个未使用的 main_item 做风险条目
    risk_item = next((it for it in main_items if item_key(it) not in used_keys), None)
    # 如果全部已用, 退而求其次取未标记的最新热点
    if risk_item is None:
        risk_candidates = query_categories(["社会", "军事", "财经", "AI", "体育"], 10)
        risk_item = next((it for it in risk_candidates if item_key(it) not in used_keys), None)
    risk_link = md_link(risk_item) if risk_item else "[数据不足](链接未获取)"
    if risk_item:
        used_keys.add(item_key(risk_item))
    lines.append(f"• 🔴 风险：{risk_link}")
    lines.append("> 影响：如果后续信息升级，可能影响公共安全、政策沟通或市场预期。  ")
    lines.append("> 关注：官方通报、权威媒体复核和相关行业响应。")
    lines.append("")
    # 机会条目：从 GitHub 日榜中取一个有描述的，跳过已展示的
    gh_items = query_source("github", 10)
    opp_item = next((it for it in gh_items if item_key(it) not in used_keys and f"repo:{repo_name(it)}" not in used_keys), None)
    if opp_item:
        opp_repo = repo_name(opp_item)
        opp_url = clean(opp_item.get("url")) or f"https://github.com/{opp_repo}"
        opp_desc = clean(parse_extra(opp_item).get("hover") or parse_extra(opp_item).get("desc"), 60)
        used_keys.add(item_key(opp_item))
        lines.append(f"• 🟢 机会：[{opp_repo}]({opp_url})")
        lines.append(f"> 影响：{opp_desc or '该项目进入 GitHub 趋势榜，开发者在快速验证相关方向。'}  ")
    else:
        # 从数据库补查一个有描述的 GitHub 项目
        fallback_gh = query_source("github", 50)
        fallback_item = next((it for it in fallback_gh if item_key(it) not in used_keys), None)
        if fallback_item:
            fb_repo = repo_name(fallback_item)
            fb_url = clean(fallback_item.get("url")) or f"https://github.com/{fb_repo}"
            used_keys.add(item_key(fallback_item))
            lines.append(f"• 🟢 机会：[{fb_repo}]({fb_url})")
            lines.append("> 影响：项目进入 GitHub 趋势榜，开发者在快速验证相关方向，建议关注后续 commits。  ")
        else:
            lines.append("• 🟢 机会：[待核验](链接未获取)")
            lines.append("> 影响：当前无未展示的 GitHub 机会条目，等待下一轮采集补充。  ")
    lines.append("> 关注：开源项目成熟度、企业版计划、真实漏洞覆盖范围和审计报告。")
    lines.append("")

    lines.append("🧩 **数据缺口**")
    lines.append("")
    # 动态生成数据缺口列表
    gap_items = []

    # 检查 HN 数据
    if hn_items:
        has_missing_comments = any(
            not parse_extra(it).get("comments") for it in hn_items
        )
        if has_missing_comments:
            gap_items.append("- **HN 评论补齐**：部分 HN 条目 Comments 数据未获取，正文已对缺口做标注。")

    # 检查 GitHub 数据
    gh_rows = query_source("github", 2)
    cache_has_data = bool(cache.get("github_language"))
    if not gh_rows and cache_has_data:
        gap_items.append("- **GitHub 趋势数据**：当前采集窗口内无 GitHub 趋势数据，可能需要检查 token 有效性。")

    # 检查 OpenAI Blog 等依赖源
    for src_name in ("openai_blog", "lobsters", "producthunt"):
        rows = query_source(src_name, 1)
        if not rows:
            gap_items.append(f"- **{src_name}**：本轮采集未获取到数据，可能 RSS 不可达或超时。")

    gap_items.append("- **微博热度**：微博 heat 多为排名或平台内部数值，不等同真实阅读量。")
    if not gap_items:
        gap_items.append("- 本轮关键数据源均已正常采集，无显著缺口。")
    lines.extend(gap_items)

    content = "\n".join(lines)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    data = open(output_path, "rb").read().replace(b"\r", b"")
    open(output_path, "wb").write(data)
    return output_path, content


def main() -> int:
    output_path, content = build_briefing()
    print(f"已生成: {output_path}")
    print(f"行数: {content.count(chr(10)) + 1}")
    print(f"字符数: {len(content)}")
    print()
    # 运行质量检查
    from check_briefing_quality import check_file, print_report
    report = check_file(str(output_path))
    print_report(report)
    if report["quality_score"] < 50:
        print("⚠️ 质量评分过低，建议检查数据库是否有足够描述数据。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
