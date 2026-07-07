"""国内科技/创投源 — 虎嗅 / 钛媒体 / 机器之心 / APPSO(爱范儿) / 硅星人(品玩)"""
from typing import Optional, Tuple
from core import rss_to_items
from sources import register


@register("huxiu", "🦊虎嗅", enabled=False, reason="需 JS 渲染/反爬 CAPTCHA，HTTP 采集长期不可用")
def source_huxiu() -> Tuple[Optional[list[dict]], Optional[str]]:
    """⚠️ 虎嗅 RSS 超时(国内CDN限速+反爬), 暂不可用"""
    return None, "虎嗅需JS渲染/反爬CAPTCHA, HTTP不可用"


@register("tmtpost", "📊钛媒体")
def source_tmtpost() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://www.tmtpost.com/rss.xml", "钛媒体", "📊", 10, 48)


@register("jiqizhixin", "🧠机器之心", enabled=False, reason="已改版为 SPA，当前无稳定公开 RSS/API")
def source_jiqizhixin() -> Tuple[Optional[list[dict]], Optional[str]]:
    """⚠️ 机器之心已改为SPA数据服务页, 无公开RSS/API"""
    return None, "机器之心已改版为SPA, HTTP不可用"


@register("appso", "📱APPSO")
def source_appso() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://www.ifanr.com/feed", "APPSO", "📱", 10, 48)


@register("pingwest", "⭐硅星人", enabled=False, reason="全站 API 405 拦截，需浏览器渲染")
def source_pingwest() -> Tuple[Optional[list[dict]], Optional[str]]:
    """⚠️ 硅星人(品玩)全站API 405拦截, 需浏览器渲染"""
    return None, "品玩全站API反爬, HTTP不可用"
