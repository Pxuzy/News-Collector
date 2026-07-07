"""
结构化日志 — JSON 格式输出, 方便 logstash/filebeat 等工具消费
"""
import json
import os
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

CST = timezone(timedelta(hours=8))


class JSONFormatter(logging.Formatter):
    """JSON 日志格式化器 — 每条日志一行 JSON"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+08:00",
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(name: str = "news-toolkit", log_dir: str = None,
                 level=logging.INFO, console: bool = True) -> logging.Logger:
    """配置结构化日志 logger

    Args:
        name: logger 名称
        log_dir: 日志目录 (None=不写文件)
        level: 日志级别
        console: 是否输出到控制台
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    formatter = JSONFormatter()

    if console:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S'))
        logger.addHandler(ch)

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(
            os.path.join(log_dir, "collector.jsonl"),
            encoding='utf-8'
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


# 默认 logger
log = setup_logger("collector")


def log_crawl_event(source: str, status: str, count: int,
                    duration_ms: int = 0, error: Optional[str] = None,
                    new: int = 0, updated: int = 0):
    """记录采集事件 (结构化)"""
    log.info(json.dumps({
        "event": "crawl",
        "source": source,
        "status": status,
        "count": count,
        "duration_ms": duration_ms,
        "new": new,
        "updated": updated,
        "error": error,
    }, ensure_ascii=False))


def log_summary(ok: int, failed: int, total: int,
                total_new: int, total_updated: int, elapsed_s: float):
    """采集汇总"""
    log.info(json.dumps({
        "event": "summary",
        "sources_ok": ok,
        "sources_failed": failed,
        "items_total": total,
        "items_new": total_new,
        "items_updated": total_updated,
        "elapsed_s": round(elapsed_s, 2),
    }, ensure_ascii=False))
