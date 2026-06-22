"""知乎 API 客户端 — 基于 openapi.zhihu.com + HMAC-SHA256 签名"""
import os
import hmac
import hashlib
import base64
import time
import json
import re
import httpx
from config import ZHIHU_TOKEN, ZHIHU_SK, ZHIHU_OAUTH_APP_ID, ZHIHU_OAUTH_APP_KEY, ZHIHU_OAUTH_REDIRECT_URI

# 清除代理环境变量，避免 SOCKS 代理导致请求失败
for _proxy_var in [
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
]:
    os.environ.pop(_proxy_var, None)

# ──────────────────── 常量 ────────────────────
BASE_URL = "https://openapi.zhihu.com"

# 可用圈子
RING_IDS = {
    "openclaw": "2001009660925334090",       # OpenClaw 人类观察员
    "a2a": "2015023739549529606",            # A2A for Reconnect
    "hackathon": "2029619126742656657",      # 黑客松脑洞补给站
}
DEFAULT_RING_ID = RING_IDS["hackathon"]


# ──────────────────── 签名 & 请求头 ────────────────────

def _build_headers(extra_info: str = "") -> dict:
    """
    构造带 HMAC-SHA256 签名的请求头。
    签名字符串: app_key:{app_key}|ts:{timestamp}|logid:{log_id}|extra_info:{extra_info}
    """
    timestamp = str(int(time.time()))
    log_id = f"request_{time.time_ns()}"

    sign_str = f"app_key:{ZHIHU_TOKEN}|ts:{timestamp}|logid:{log_id}|extra_info:{extra_info}"
    h = hmac.new(ZHIHU_SK.encode(), sign_str.encode(), hashlib.sha256)
    sign = base64.b64encode(h.digest()).decode()

    return {
        "X-App-Key": ZHIHU_TOKEN,
        "X-Timestamp": timestamp,
        "X-Log-Id": log_id,
        "X-Sign": sign,
        "X-Extra-Info": extra_info,
        "Content-Type": "application/json",
    }


# ──────────────────── 通用请求 ────────────────────

async def _get(path: str, params: dict | None = None) -> dict:
    """通用 GET 请求"""
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.get(url, headers=_build_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, data: dict | None = None) -> dict:
    """通用 POST 请求"""
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.post(url, headers=_build_headers(), json=data)
        resp.raise_for_status()
        return resp.json()


# ──────────────────── 知乎搜索 ────────────────────

async def zhihu_search(query: str, limit: int = 10) -> dict:
    """
    知乎站内搜索
    GET /api/v1/content/zhihu_search
    返回：文章/问答标题、摘要、作者、点赞数、评论数等
    """
    return await _get("/api/v1/content/zhihu_search", {
        "q": query,
        "limit": limit,
    })


async def global_search(query: str, limit: int = 10) -> dict:
    """
    全网搜索
    GET /api/v1/content/global_search
    返回：网页标题、摘要、作者、相关性分数等
    """
    return await _get("/api/v1/content/global_search", {
        "q": query,
        "limit": limit,
    })


# ──────────────────── 热榜 ────────────────────

async def get_hot_list(limit: int = 20) -> dict:
    """
    获取知乎热榜
    GET /api/v1/content/hot_list
    """
    return await _get("/api/v1/content/hot_list", {
        "limit": limit,
    })


# ──────────────────── 圈子操作 ────────────────────

async def get_ring_detail(ring_id: str = DEFAULT_RING_ID) -> dict:
    """
    获取圈子帖子列表和评论
    GET /openapi/ring/detail
    """
    return await _get("/openapi/ring/detail", {"ring_id": ring_id})


async def publish_pin(content: str, ring_id: str = DEFAULT_RING_ID) -> dict:
    """
    发布一条想法到圈子
    POST /openapi/publish/pin
    """
    return await _post("/openapi/publish/pin", {
        "content": content,
        "ring_id": ring_id,
    })


async def reaction(target_id: str, target_type: str = "pin", action: str = "like") -> dict:
    """
    点赞/取消点赞
    POST /openapi/reaction
    """
    return await _post("/openapi/reaction", {
        "target_id": target_id,
        "target_type": target_type,
        "action": action,
    })


async def create_comment(target_id: str, content: str, target_type: str = "pin") -> dict:
    """
    发表评论 / 回复评论
    POST /openapi/comment/create
    """
    return await _post("/openapi/comment/create", {
        "target_id": target_id,
        "target_type": target_type,
        "content": content,
    })


async def get_comments(target_id: str, target_type: str = "pin") -> dict:
    """
    获取评论列表
    GET /openapi/comment/list
    """
    return await _get("/openapi/comment/list", {
        "target_id": target_id,
        "target_type": target_type,
    })


# ──────────────────── 关注流 ────────────────────

async def get_following_feed(limit: int = 20) -> dict:
    """
    获取关注人动态与内容流
    GET /openapi/feed/following
    """
    return await _get("/openapi/feed/following", {"limit": limit})


async def get_following_list(limit: int = 20) -> dict:
    """
    获取关注列表
    GET /openapi/user/following
    """
    return await _get("/openapi/user/following", {"limit": limit})


async def get_followers_list(limit: int = 20) -> dict:
    """
    获取粉丝列表
    GET /openapi/user/followers
    """
    return await _get("/openapi/user/followers", {"limit": limit})


# ──────────────────── Agent 直答 ────────────────────

async def agent_chat(messages: list[dict], temperature: float = 0.7) -> str:
    """
    知乎 Agent 直答
    POST /v1/chat/completions
    基于知乎优质内容生成回答
    """
    url = f"{BASE_URL}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=60, proxy=None) as client:
        resp = await client.post(
            url,
            headers=_build_headers(),
            json={
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("message", {}).get("content", "")
        return json.dumps(data, ensure_ascii=False)


# ──────────────────── 辅助函数 ────────────────────

async def fetch_user_profile(profile_url_or_id: str) -> dict | None:
    """根据知乎个人主页 URL 或 slug 获取用户信息（名称、头像、粉丝数、赞同数）"""
    slug = profile_url_or_id.strip().rstrip("/")
    if "/" in slug:
        slug = slug.rstrip("/").rsplit("/", 1)[-1]
    slug = slug.split("?")[0]

    profile = {
        "slug": slug,
        "zhihu_name": "",
        "avatar_url": "",
        "followers_count": 0,
        "upvotes_count": 0,
    }

    try:
        # 使用知乎 v4 API 获取用户信息（无需登录，公开接口）
        api_url = f"https://www.zhihu.com/api/v4/members/{slug}?include=follower_count,voteup_count,avatar_url"
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, proxy=None) as client:
            resp = await client.get(api_url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": "https://www.zhihu.com/",
            })
            if resp.status_code == 200:
                data = resp.json()
                profile["zhihu_name"] = data.get("name", "")
                profile["avatar_url"] = data.get("avatar_url", "")
                profile["followers_count"] = data.get("follower_count", 0)
                profile["upvotes_count"] = data.get("voteup_count", 0)
                if profile["zhihu_name"]:
                    return profile

            # 如果 v4 API 失败，回退到爬 HTML 页面
            print(f"[zhihu_client] v4 API failed ({resp.status_code}), falling back to HTML")
            url = f"https://www.zhihu.com/people/{slug}"
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            if resp.status_code != 200:
                print(f"[zhihu_client] fetch_user_profile: HTTP {resp.status_code}")
                # 即使获取不到详细信息，也用 slug 作为用户名返回
                profile["zhihu_name"] = slug
                return profile

            html = resp.text
            title_match = re.search(r"<title[^>]*>(.*?)(?:的知乎个人主页| - 知乎)</title>", html)
            if title_match:
                profile["zhihu_name"] = title_match.group(1).strip()

            avatar_match = re.search(r'<meta\s+property="og:image"\s+content="(.*?)"', html)
            if avatar_match:
                profile["avatar_url"] = avatar_match.group(1)

            init_data = re.search(r'id="js-initialData"\s+type="text/json">(.*?)</script>', html)
            if init_data:
                try:
                    data = json.loads(init_data.group(1))
                    entities = data.get("initialState", {}).get("entities", {}).get("users", {})
                    for uid, uinfo in entities.items():
                        if uinfo.get("urlToken") == slug or uinfo.get("id") == slug:
                            profile["zhihu_name"] = uinfo.get("name", profile["zhihu_name"])
                            profile["avatar_url"] = uinfo.get("avatarUrl", profile["avatar_url"])
                            profile["followers_count"] = uinfo.get("followerCount", 0)
                            profile["upvotes_count"] = uinfo.get("voteupCount", 0) or uinfo.get("thankCount", 0)
                            break
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    print(f"[zhihu_client] parse initialData failed: {e}")

        # 即使获取不到详细信息，也允许用 slug 登录
        if not profile["zhihu_name"]:
            profile["zhihu_name"] = slug
        return profile

    except Exception as e:
        print(f"[zhihu_client] fetch_user_profile error: {e}")
        # 即使发生异常，也允许用 slug 登录（避免海外服务器网络问题导致登录失败）
        if not profile["zhihu_name"]:
            profile["zhihu_name"] = slug
        return profile

async def fetch_content_by_url(url: str) -> dict | None:
    """
    通过 URL 获取知乎内容详情
    策略：用知乎 v4 API 直接获取回答/文章的完整正文（需浏览器 cookies）
    """
    content_info = {
        "url": url, "type": "unknown",
        "title": "", "summary": "", "author": "", "body": "",
    }

    try:
        cookie_dict = _get_browser_cookies()
        headers = {
            **_BROWSER_HEADERS,
            "Referer": "https://www.zhihu.com/",
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, proxy=None, cookies=cookie_dict) as client:

            # ── 回答：/api/v4/answers/{answer_id} ──
            if "question" in url and "answer" in url:
                content_info["type"] = "answer"
                answer_match = re.search(r"answer/(\d+)", url)
                question_match = re.search(r"question/(\d+)", url)
                if answer_match:
                    answer_id = answer_match.group(1)
                    resp = await client.get(
                        f"https://www.zhihu.com/api/v4/answers/{answer_id}",
                        headers=headers,
                        params={"include": "content,excerpt,author.name"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        q = data.get("question", {})
                        content_info["title"] = q.get("title", data.get("title", ""))
                        content_info["summary"] = _clean_html(data.get("excerpt", ""))
                        author = data.get("author", {})
                        content_info["author"] = author.get("name", "") if isinstance(author, dict) else ""
                        content_info["body"] = _clean_html(data.get("content", ""))
                elif question_match:
                    # 只有 question id 没有 answer id，获取问题详情
                    question_id = question_match.group(1)
                    resp = await client.get(
                        f"https://www.zhihu.com/api/v4/questions/{question_id}",
                        headers=headers,
                        params={"include": "detail,excerpt"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content_info["title"] = data.get("title", "")
                        content_info["summary"] = _clean_html(data.get("excerpt", ""))
                        content_info["body"] = _clean_html(data.get("detail", data.get("excerpt", "")))

            # ── 文章：/api/v4/articles/{article_id} ──
            elif "zhuanlan" in url or "/p/" in url:
                content_info["type"] = "article"
                match = re.search(r"/p/(\d+)", url)
                if match:
                    article_id = match.group(1)
                    resp = await client.get(
                        f"https://www.zhihu.com/api/v4/articles/{article_id}",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content_info["title"] = data.get("title", "")
                        content_info["summary"] = _clean_html(data.get("excerpt", ""))
                        author = data.get("author", {})
                        content_info["author"] = author.get("name", "") if isinstance(author, dict) else ""
                        content_info["body"] = _clean_html(data.get("content", ""))

            # ── 想法（pin）──
            elif "pin" in url:
                content_info["type"] = "pin"
                match = re.search(r"pin/(\d+)", url)
                if match:
                    pin_id = match.group(1)
                    resp = await client.get(
                        f"https://www.zhihu.com/api/v4/pins/{pin_id}",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        # 想法没有 title，用内容前50字做标题
                        raw_content = ""
                        for block in data.get("content", []):
                            if block.get("type") == "text":
                                raw_content += block.get("content", "")
                        raw_content = _clean_html(raw_content) if raw_content else _clean_html(data.get("excerpt_title", ""))
                        content_info["title"] = raw_content[:50] if raw_content else "想法"
                        content_info["body"] = raw_content
                        content_info["summary"] = raw_content[:200]
                        author = data.get("author", {})
                        content_info["author"] = author.get("name", "") if isinstance(author, dict) else ""

            # ── 兜底：直接抓页面提取 meta 信息 ──
            if not content_info["body"]:
                print(f"[zhihu_client] v4 API 未获取到正文，尝试抓取页面: {url}")
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    title_match = re.search(r"<title>(.*?)</title>", html)
                    if title_match and not content_info["title"]:
                        content_info["title"] = title_match.group(1).replace(" - 知乎", "").strip()
                    desc_match = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html)
                    if desc_match:
                        content_info["summary"] = desc_match.group(1)
                    # 从 js-initialData 提取正文
                    init_data = re.search(r'<script\s+id="js-initialData"[^>]*>(.*?)</script>', html, re.DOTALL)
                    if init_data:
                        try:
                            jd = json.loads(init_data.group(1))
                            # 尝试从 entities 中提取
                            entities = jd.get("initialState", {}).get("entities", {})
                            for answers in entities.get("answers", {}).values():
                                body = answers.get("content", "")
                                if body:
                                    content_info["body"] = _clean_html(body)
                                    if not content_info["title"]:
                                        content_info["title"] = answers.get("question", {}).get("title", "")
                                    break
                            if not content_info["body"]:
                                for articles in entities.get("articles", {}).values():
                                    body = articles.get("content", "")
                                    if body:
                                        content_info["body"] = _clean_html(body)
                                        if not content_info["title"]:
                                            content_info["title"] = articles.get("title", "")
                                        break
                        except (json.JSONDecodeError, KeyError, TypeError):
                            pass

    except Exception as e:
        print(f"[zhihu_client] fetch_content_by_url error: {e}")

    return content_info


async def publish_recommendation_pin(
    title: str, score: float, reason: str, url: str,
    ring_id: str = DEFAULT_RING_ID,
) -> dict | None:
    """将推荐成功的内容发布到知乎圈子"""
    content = f"""刘看山推荐 | 综合评分 {score:.1f}/10

📄 {title}

💬 推荐理由：{reason}

🔗 原文链接：{url}

#刘看山推荐 #优质内容发现"""

    try:
        return await publish_pin(content, ring_id=ring_id)
    except Exception as e:
        print(f"[zhihu_client] publish_recommendation_pin error: {e}")
        return None


# ──────────────────── 用户内容获取 ────────────────────

def _get_browser_cookies() -> dict:
    """尝试从 Edge 浏览器获取知乎 cookies"""
    try:
        import browser_cookie3
        cookies = browser_cookie3.edge(domain_name='.zhihu.com')
        return {c.name: c.value for c in cookies}
    except Exception as e:
        print(f"[zhihu_client] 获取浏览器 cookies 失败: {e}")
        return {}


_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


async def discover_user_slug(name_or_uid: str, hash_id: str = "") -> str | None:
    """
    通过知乎 v4 API 尝试发现用户的 URL slug。
    策略:
    1. 如果有 hash_id，用 v4 members API 直接查
    2. 搜索用户名，从结果中匹配
    """
    cookie_dict = _get_browser_cookies()
    if not cookie_dict:
        return None

    headers = {**_BROWSER_HEADERS, "Referer": "https://www.zhihu.com/search"}

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, proxy=None, cookies=cookie_dict) as client:
            # 方法1: 用 hash_id 直接查 (如果 hash_id 就是 url_token)
            if hash_id:
                resp = await client.get(
                    f"https://www.zhihu.com/api/v4/members/{hash_id}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    slug = data.get("url_token", "")
                    if slug:
                        print(f"[zhihu_client] 发现 slug (via hash_id): {slug}")
                        return slug

            # 方法2: 搜索用户名
            resp = await client.get(
                "https://www.zhihu.com/api/v4/search_v3",
                headers=headers,
                params={"q": name_or_uid, "t": "people", "offset": 0, "limit": 5},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    obj = item.get("object", {})
                    if obj.get("name") == name_or_uid or str(obj.get("id")) == name_or_uid:
                        slug = obj.get("url_token", "")
                        if slug:
                            print(f"[zhihu_client] 发现 slug (via search): {slug}")
                            return slug
    except Exception as e:
        print(f"[zhihu_client] discover_user_slug error: {e}")
    return None


async def fetch_user_content(slug: str, limit: int = 20) -> list[dict]:
    """
    通过知乎 v4 API 获取用户发布的回答和文章。
    需要浏览器 cookies（知乎 v4 API 不对外开放）。
    返回: [{ title, excerpt, url, type, voteup_count, comment_count, created_time }]
    """
    cookie_dict = _get_browser_cookies()
    if not cookie_dict:
        print("[zhihu_client] 无浏览器 cookies，无法获取用户内容")
        return []

    contents = []
    headers = {**_BROWSER_HEADERS, "Referer": f"https://www.zhihu.com/people/{slug}"}

    async with httpx.AsyncClient(timeout=15, follow_redirects=True, proxy=None, cookies=cookie_dict) as client:
        # 获取回答
        try:
            resp = await client.get(
                f"https://www.zhihu.com/api/v4/members/{slug}/answers",
                headers=headers,
                params={
                    "include": "data[*].content,excerpt,created_time,updated_time,voteup_count,comment_count,question",
                    "offset": 0,
                    "limit": limit,
                    "sort_by": "created",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    q = item.get("question", {})
                    contents.append({
                        "title": q.get("title", ""),
                        "excerpt": _clean_html(item.get("excerpt", "")),
                        "url": f"https://www.zhihu.com/question/{q.get('id')}/answer/{item.get('id')}",
                        "type": "answer",
                        "voteup_count": item.get("voteup_count", 0),
                        "comment_count": item.get("comment_count", 0),
                        "created_time": item.get("created_time", 0),
                    })
        except Exception as e:
            print(f"[zhihu_client] fetch answers error: {e}")

        # 获取文章
        try:
            resp = await client.get(
                f"https://www.zhihu.com/api/v4/members/{slug}/articles",
                headers=headers,
                params={
                    "include": "data[*].content,excerpt,created,updated,voteup_count,comment_count",
                    "offset": 0,
                    "limit": limit,
                    "sort_by": "created",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    contents.append({
                        "title": item.get("title", ""),
                        "excerpt": _clean_html(item.get("excerpt", "")),
                        "url": f"https://zhuanlan.zhihu.com/p/{item.get('id')}",
                        "type": "article",
                        "voteup_count": item.get("voteup_count", 0),
                        "comment_count": item.get("comment_count", 0),
                        "created_time": item.get("created", 0),
                    })
        except Exception as e:
            print(f"[zhihu_client] fetch articles error: {e}")

        # 获取想法 (pins)
        try:
            resp = await client.get(
                f"https://www.zhihu.com/api/v4/members/{slug}/pins",
                headers=headers,
                params={
                    "offset": 0,
                    "limit": limit,
                    "sort_by": "created",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    # 想法的内容在 content 字段中，是一个数组
                    raw_content = ""
                    for block in item.get("content", []):
                        if block.get("type") == "text":
                            raw_content += block.get("content", "")
                    raw_content = _clean_html(raw_content) if raw_content else ""
                    # 如果 content 为空，尝试 excerpt_title
                    if not raw_content:
                        raw_content = item.get("excerpt_title", "") or ""
                    pin_title = raw_content[:50] + ("..." if len(raw_content) > 50 else "") if raw_content else "想法"
                    contents.append({
                        "title": pin_title,
                        "excerpt": raw_content[:200] if raw_content else "",
                        "url": f"https://www.zhihu.com/pin/{item.get('id')}",
                        "type": "pin",
                        "voteup_count": item.get("like_count", 0) or item.get("voteup_count", 0),
                        "comment_count": item.get("comment_count", 0),
                        "created_time": item.get("created", 0) or item.get("created_time", 0),
                    })
            else:
                print(f"[zhihu_client] fetch pins status: {resp.status_code}")
        except Exception as e:
            print(f"[zhihu_client] fetch pins error: {e}")

    # 按创建时间排序（最新在前）
    contents.sort(key=lambda x: x.get("created_time", 0), reverse=True)
    return contents[:limit]


def _clean_html(text: str) -> str:
    """清理 HTML 标签"""
    return re.sub(r"<[^>]+>", "", text).strip()


# ──────────────────── OAuth API (Bearer Token) ────────────────────

def _check_oauth_response(data: dict | list) -> dict | list:
    """检查知乎 OAuth API 的响应，处理 HTTP 200 中返回的错误"""
    if isinstance(data, dict) and "code" in data and data["code"] not in (0, None, 20000):
        # code=20000 是知乎 token 接口的正常响应码，不是错误
        msg = data.get("data", data.get("message", "未知错误"))
        raise ValueError(f"知乎 OAuth 错误 (code={data['code']}): {msg}")
    return data


async def exchange_code_for_token(code: str) -> dict:
    """
    用授权码换取 access_token
    POST /access_token (application/x-www-form-urlencoded)
    返回: {"access_token": str, "token_type": "Bearer", "expires_in": int}
    """
    url = f"{BASE_URL}/access_token"
    print(f"[oauth] exchange_code_for_token: code={code[:20]}... redirect_uri={ZHIHU_OAUTH_REDIRECT_URI}")
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.post(url, data={
            "app_id": ZHIHU_OAUTH_APP_ID,
            "app_key": ZHIHU_OAUTH_APP_KEY,
            "grant_type": "authorization_code",
            "redirect_uri": ZHIHU_OAUTH_REDIRECT_URI,
            "code": code,
        })
        resp.raise_for_status()
        data = resp.json()
        print(f"[oauth] Zhihu response: {data}")
        _check_oauth_response(data)
        return data


async def get_oauth_user_info(access_token: str) -> dict:
    """
    获取 OAuth 用户信息
    GET /user  Authorization: Bearer {token}
    返回: {"uid": int, "fullname": str, "gender": str, "headline": str,
           "description": str, "avatar_path": str, "phone_no": str, "email": str}
    """
    url = f"{BASE_URL}/user"
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.get(url, headers={
            "Authorization": f"Bearer {access_token}",
        })
        resp.raise_for_status()
        data = resp.json()
        _check_oauth_response(data)
        return data


async def get_user_moments_oauth(access_token: str) -> list[dict]:
    """
    获取用户关注动态
    GET /user/moments  Authorization: Bearer {token}
    返回: data 数组，每项含 actor, action_text, action_time, target
    """
    url = f"{BASE_URL}/user/moments"
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.get(url, headers={
            "Authorization": f"Bearer {access_token}",
        })
        resp.raise_for_status()
        data = resp.json()
        _check_oauth_response(data)
        # 返回格式: {"data": [...]}
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, list) else []


async def get_user_followers_oauth(access_token: str, page: int = 0, per_page: int = 10) -> list[dict]:
    """
    获取用户粉丝列表 (OAuth)
    GET /user/followers  Authorization: Bearer {token}
    返回: 用户对象数组
    """
    url = f"{BASE_URL}/user/followers"
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.get(url, headers={
            "Authorization": f"Bearer {access_token}",
        }, params={"page": page, "per_page": per_page})
        resp.raise_for_status()
        data = resp.json()
        _check_oauth_response(data)
        return data if isinstance(data, list) else []