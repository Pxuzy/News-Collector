#!/usr/bin/env python
"""
数据缺口补齐工具 v2 — 动态补齐 HN + GitHub 缺失字段

自动从 news.db 读取实际热榜数据，然后从 API 补齐缺失字段。
采集器 cron 自动调用此脚本，输出缓存供简报生成使用。
"""
import sys, os, json, urllib.request, time, sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(SCRIPT_DIR, '..', 'cron', 'output', '_data_gaps_cache.json')
NEWS_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "news.db"
)

GITHUB_API_CACHE = {}  # memoize API calls

def fetch_github_weekly(limit=10):
    """从 GitHub Trending Weekly 爬取周榜（支持重试）"""
    import re
    repos = []
    url = 'https://github.com/trending?since=weekly'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml'
    }

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=20)
            chunks = []
            while True:
                try:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                except Exception:
                    break
            html = b''.join(chunks).decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < 2:
                print(f'  ⚠️ 周榜重试 {attempt+1}: {e}')
                import time
                time.sleep(3)
                continue
            print(f'[GitHub Weekly] 爬取失败（重试{attempt+1}次）: {e}')
            return repos

        # === 解析 HTML ===
        # 按 <article> 块分割
        articles = re.findall(
            r'<article[^>]*class="Box-row[^"]*"[^>]*>(.*?)</article>',
            html, re.DOTALL
        )
        if not articles:
            # fallback: 按 <h2> 定位
            repo_links = re.findall(
                r'<h2[^>]*class="h3[^"]*"[^>]*>.*?<a[^>]*href="/([^"]+)"',
                html, re.DOTALL
            )
            for repo in repo_links[:limit]:
                repos.append({'repo': repo.strip(), 'stars': 0, 'description': ''})
            print(f'[GitHub Weekly] 获取 {len(repos)} 个（基础模式）')
            return repos

        for art_html in articles[:limit]:
            if len(art_html) < 50:
                continue
            # repo 名称 — 只匹配 <h2> 里的链接
            repo_match = re.search(
                r'<h2[^>]*>.*?<a[^>]*href="/([^/]+/[^/"]+)"',
                art_html, re.DOTALL
            )
            if not repo_match:
                continue
            repo = repo_match.group(1).strip()

            # total stars — stargazers 链接里
            star_match = re.search(
                r'stargazers[^>]*>\s*(?:<svg[^>]*>.*?</svg>\s*)?([\d,]+)\s*<',
                art_html, re.DOTALL
            )
            total_stars = 0
            if star_match:
                total_stars = int(star_match.group(1).replace(',', ''))

            # 描述
            desc_match = re.search(
                r'<p[^>]*class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
                art_html, re.DOTALL
            )
            desc = ''
            if desc_match:
                desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()[:120]

            repos.append({
                'repo': repo,
                'stars': total_stars,
                'description': desc
            })

        if repos:
            print(f'[GitHub Weekly] 获取 {len(repos)} 个周榜仓库')
            return repos
        else:
            print(f'[GitHub Weekly] 第{attempt+1}次解析为空，重试...')
            import time
            time.sleep(2)

    print('[GitHub Weekly] 3次尝试均失败')
    return repos

def fetch_hn_comments(limit=15):
    """从 HN Algolia API 获取 Points + Comments"""
    try:
        url = f'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Hermes/1.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        results = {}
        for hit in data.get('hits', []):
            title = hit.get('title', '')
            hn_id = hit.get('objectID', '')
            results[title] = {
                'points': hit.get('points', 0),
                'comments': hit.get('num_comments', 0),
                'hn_url': f'https://news.ycombinator.com/item?id={hn_id}',
                'url': hit.get('url') or f'https://news.ycombinator.com/item?id={hn_id}'
            }
        return results
    except Exception as e:
        return {'_error': str(e)}

def fetch_github_repo_info(repo_name):
    """从 GitHub API 获取单个仓库的语言、Stars、Topics"""
    if repo_name in GITHUB_API_CACHE:
        return GITHUB_API_CACHE[repo_name]
    try:
        url = f'https://api.github.com/repos/{repo_name}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Hermes/1.0'})
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())
        result = {
            'language': data.get('language'),
            'stars': data.get('stargazers_count'),
            'description': data.get('description', '')[:120],
            'topics': data.get('topics', [])
        }
        GITHUB_API_CACHE[repo_name] = result
        return result
    except Exception as e:
        result = {'language': None, 'stars': None, 'description': None, 'error': str(e)[:50]}
        GITHUB_API_CACHE[repo_name] = result
        return result

def get_trending_repos_from_db(limit=10):
    """从 news.db 读取实际 GitHub 日榜热 repo"""
    repos = []
    try:
        conn = sqlite3.connect(NEWS_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # 取最新的 github 条目
        cur.execute("""
            SELECT title, url, heat FROM news_items
            WHERE source = 'github' AND COALESCE(is_duplicate,0)=0
            ORDER BY heat_score DESC, first_seen DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        for row in rows:
            title = row['title'].replace(' / ', '/').strip()
            url = row['url']
            # 从 title 提取 owner/repo 格式
            if '/' in title and not title.startswith('http'):
                repos.append(title)
            elif 'github.com' in url:
                parts = url.replace('https://github.com/', '').split('/')
                if len(parts) >= 2:
                    repos.append(f"{parts[0]}/{parts[1]}")
        conn.close()
    except Exception as e:
        print(f"[GitHub] DB 读取出错: {e}")
    return repos

def fetch_all_github_repos(repo_names):
    """批量获取 GitHub 仓库语言等信息"""
    results = {}
    for i, repo in enumerate(repo_names):
        info = fetch_github_repo_info(repo)
        results[repo] = info
        print(f"[GitHub] {i+1}/{len(repo_names)} {repo} → {info.get('language') or '?'} ⭐{info.get('stars') or '?'}")
        time.sleep(0.3)  # rate limit 保护
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser(description='补齐 news.db 数据缺口 v2')
    parser.add_argument('--sources', nargs='+',
                       choices=['hn', 'github', 'all'],
                       default=['all'])
    parser.add_argument('--github-limit', type=int, default=10,
                       help='GitHub 最多补多少个仓库 (默认10)')
    args = parser.parse_args()

    result = {}
    sources = args.sources

    # === HN 补齐 ===
    if 'hn' in sources or 'all' in sources:
        hn_data = fetch_hn_comments()
        result['hn_comments'] = hn_data
        count = len(hn_data)
        print(f'[HN] 获取 {count} 条')

    # === GitHub 补齐（动态读取 DB 实际热榜）===
    if 'github' in sources or 'all' in sources:
        trending_repos = get_trending_repos_from_db(args.github_limit)
        # 去重
        seen = set()
        unique_repos = []
        for r in trending_repos:
            if r not in seen:
                seen.add(r)
                unique_repos.append(r)

        if unique_repos:
            print(f"[GitHub] 从 DB 加载 {len(unique_repos)} 个实际热榜仓库，开始补齐 language...")
            gh_data = fetch_all_github_repos(unique_repos)
        else:
            # 兜底：DB 没数据时 fallback 到已知热榜
            print(f"[GitHub] DB 无数据，使用已知热榜仓库")
            fallback = [
                'usestrix/strix', 'msitarzewski/agency-agents',
                'browser-use/video-use', 'HKUDS/Vibe-Trading',
                'microsoft/AI-For-Beginners', 'obra/superpowers',
                'ChromeDevTools/chrome-devtools-mcp',
                'deepseek-ai/DeepSeek-V4', 'n8n-io/n8n',
                'ripienaar/free-for-dev'
            ]
            gh_data = fetch_all_github_repos(fallback)
        result['github_language'] = gh_data

    # === GitHub 周榜补齐（从 HTML 直接爬取）===
    if 'github' in sources or 'all' in sources:
        weekly_data = fetch_github_weekly(limit=10)
        if weekly_data:
            result['github_weekly'] = weekly_data
            # 对周榜仓库也补 language（取没在日榜中出现的）
            weekly_repos = [w['repo'] for w in weekly_data]
            daily_repos = list(result.get('github_language', {}).keys())
            need_lang = [r for r in weekly_repos if r not in daily_repos]
            if need_lang:
                print(f"[GitHub Weekly] 补 language for {len(need_lang)} 个新仓库...")
                lang_data = fetch_all_github_repos(need_lang[:5])  # 最多补5个
                if 'github_language' not in result:
                    result['github_language'] = {}
                result['github_language'].update(lang_data)

    # === 写入缓存 ===
    if result:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
        print(f'[Cache] 已保存到 {CACHE_PATH}')

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
