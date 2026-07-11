"""
来源基础模块 — 定义 SourceFunc 类型和装饰器
自动导入所有来源模块
"""
from typing import Optional, Callable

SourceFunc = Callable[[], tuple[Optional[list[dict]], Optional[str]]]

_REGISTRY: dict[str, tuple[str, SourceFunc]] = {}
_DISABLED_REGISTRY: dict[str, dict[str, str]] = {}

def register(name: str, label: str, enabled: bool = True, reason: str = ""):
    def decorator(func: SourceFunc) -> SourceFunc:
        if enabled:
            _REGISTRY[name] = (label, func)
        else:
            _DISABLED_REGISTRY[name] = {
                "label": label,
                "reason": reason,
                "function": getattr(func, "__name__", ""),
            }
        return func
    return decorator

def get_source(name: str) -> tuple[str, SourceFunc] | None:
    return _REGISTRY.get(name)

def all_sources() -> dict[str, tuple[str, SourceFunc]]:
    return dict(_REGISTRY)

def disabled_sources() -> dict[str, dict[str, str]]:
    return dict(_DISABLED_REGISTRY)

def core_sources() -> list[str]:
    """返回核心源 (约30个, 按价值排序)"""
    return [
        "wallstreetcn", "jin10", "xueqiu",
        "techcrunch", "arstechnica", "techmeme",
        "hackernews", "reddit", "github",
        "aihot", "huggingface", "openai_blog",
        "bbc_world", "googlenews", "reuters",
        "baidu", "zhihu", "toutiao", "weibo",
        "thepaper", "36kr",
        "v2ex", "juejin", "ithome",
        "dongqiudi", "bilibili_pop", "sspai",
        "arxiv", "tldr_ai", "producthunt",
        "tmtpost", "appso",
    ]

def all_source_names() -> list[str]:
    """返回全部注册源列表"""
    return list(_REGISTRY.keys())


# ─── 源元数据（供简报使用） ───
# 中文名映射
SOURCE_NAMES_CN = {
    "baidu": "百度", "zhihu": "知乎", "toutiao": "头条", "weibo": "微博",
    "douyin": "抖音", "bilibili": "B站", "bilibili_pop": "B站热门",
    "thepaper": "澎湃", "tieba": "贴吧", "hupu": "虎扑",
    "ithome": "IT之家", "ifeng": "凤凰网", "36kr": "36氪",
    "tencent": "腾讯", "v2ex": "V2EX", "sspai": "少数派",
    "douban": "豆瓣", "hackernews": "HackerNews", "reddit": "Reddit",
    "github": "GitHub", "huggingface": "HuggingFace", "aihot": "AIHOT",
    "arxiv": "arXiv", "tldr_ai": "TLDR AI", "producthunt": "ProductHunt",
    "lobsters": "Lobsters", "devto": "Dev.to",
    "openai_blog": "OpenAI", "google_blog": "Google AI",
    "techcrunch": "TechCrunch", "arstechnica": "Ars Technica",
    "wired": "Wired", "techmeme": "Techmeme", "tmtpost": "钛媒体",
    "juejin": "掘金", "nowcoder": "牛客", "dongqiudi": "懂球帝",
    "appso": "APPSO", "ifanr": "爱范儿",
    "wallstreetcn": "华尔街见闻", "jin10": "金十", "xueqiu": "雪球",
    "bbc_world": "BBC", "guardian": "卫报", "aljazeera": "半岛",
    "reuters": "路透", "france24": "France24",
    "googlenews": "Google新闻", "googlenews_cn": "谷歌新闻(中文)",
    "googlenews_tech": "谷歌新闻(科技)", "googlenews_business": "谷歌新闻(商业)",
}

# 源分组（供简报分类查询）
SOURCE_GROUPS = {
    "domestic": ["baidu", "weibo", "douyin", "toutiao", "zhihu",
                 "bilibili", "bilibili_pop", "thepaper", "tieba", "hupu",
                 "ithome", "ifeng", "36kr", "tencent", "v2ex", "sspai", "douban"],
    "intl": ["hackernews", "reddit", "github",
             "bbc_world", "guardian", "aljazeera", "reuters", "france24",
             "googlenews", "googlenews_cn", "googlenews_tech", "googlenews_business"],
    "finance": ["wallstreetcn", "jin10", "xueqiu"],
    "tech_foreign": ["techcrunch", "arstechnica", "wired", "techmeme"],
    "tech_china": ["tmtpost", "juejin", "appso", "ifanr"],
    "ai": ["aihot", "huggingface", "arxiv", "tldr_ai",
           "producthunt", "lobsters", "devto",
           "openai_blog", "google_blog"],
    "sports": ["dongqiudi"],
}


def get_source_cn(name: str) -> str:
    """返回源的中文显示名"""
    return SOURCE_NAMES_CN.get(name, name)


def get_group_sources(group: str) -> list[str]:
    """返回指定分组的源列表"""
    return SOURCE_GROUPS.get(group, [])


def all_group_names() -> list[str]:
    """返回所有分组名"""
    return list(SOURCE_GROUPS.keys())


# 自动导入各源模块（触发 @register 装饰器）
from . import domestic, bilibili, douyin, wallstreet, github, international, ai, extra  # noqa: E402,F401
from . import tech_foreign, tech_china  # noqa: E402,F401
