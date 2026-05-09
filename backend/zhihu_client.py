"""知乎 API 客户端"""
import httpx
import json
from config import ZHIHU_TOKEN, ZHIHU_SK

# API 基础地址
RING_BASE = "https://www.zhihu.com/ring/moltbook/api"
CONTENT_BASE = "https://www.zhihu.com/ring/moltbook/api"

# 通用请求头
def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "x-api-token": ZHIHU_TOKEN,
        "x-api-key": ZHIHU_SK,
    }


async def _get(path: str, params: dict | None = None) -> dict:
    """通用 GET 请求"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{RING_BASE}{path}", headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, data: dict | None = None) -> dict:
    """通用 POST 请求"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{RING_BASE}{path}", headers=_headers(), json=data)
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

async def get_ring_detail(ring_id: str = "") -> dict:
    """
    获取圈子帖子列表
    GET /openapi/ring/detail
    """
    params = {}
    if ring_id:
        params["ring_id"] = ring_id
    return await _get("/openapi/ring/detail", params)


async def publish_pin(content: str) -> dict:
    """
    发布一条想法到圈子
    POST /openapi/publish/pin
    """
    return await _post("/openapi/publish/pin", {
        "content": content,
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
    发表评论
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
    获取关注人动态
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
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{RING_BASE}/v1/chat/completions",
            headers=_headers(),
            json={
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # 尝试提取回答内容
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("message", {}).get("content", "")
        return json.dumps(data, ensure_ascii=False)


# ──────────────────── 辅助函数 ────────────────────

async def fetch_content_by_url(url: str) -> dict | None:
    """
    通过 URL 获取知乎内容详情
    策略：从 URL 提取关键词，通过搜索 API 获取内容
    """
    import re

    # 从 URL 提取内容类型和 ID
    # 知乎回答: https://www.zhihu.com/question/xxx/answer/xxx
    # 知乎文章: https://zhuanlan.zhihu.com/p/xxx
    # 知乎想法: https://www.zhihu.com/pin/xxx

    content_info = {"url": url, "type": "unknown", "title": "", "summary": "", "author": "", "body": ""}

    try:
        # 尝试通过搜索获取内容
        # 从 URL 中提取可能的关键词
        if "question" in url:
            content_info["type"] = "answer"
            # 提取问题 ID
            match = re.search(r"question/(\d+)", url)
            if match:
                question_id = match.group(1)
                search_result = await zhihu_search(f"question:{question_id}", limit=5)
                if search_result and "data" in search_result:
                    items = search_result["data"]
                    if items:
                        item = items[0]
                        content_info["title"] = item.get("title", "")
                        content_info["summary"] = item.get("summary", item.get("excerpt", ""))
                        content_info["author"] = item.get("author", {}).get("name", "") if isinstance(item.get("author"), dict) else item.get("author", "")
                        content_info["body"] = item.get("content", item.get("summary", ""))
        elif "zhuanlan" in url:
            content_info["type"] = "article"
            match = re.search(r"/p/(\d+)", url)
            if match:
                article_id = match.group(1)
                search_result = await zhihu_search(f"article:{article_id}", limit=5)
                if search_result and "data" in search_result:
                    items = search_result["data"]
                    if items:
                        item = items[0]
                        content_info["title"] = item.get("title", "")
                        content_info["summary"] = item.get("summary", item.get("excerpt", ""))
                        content_info["author"] = item.get("author", {}).get("name", "") if isinstance(item.get("author"), dict) else item.get("author", "")
                        content_info["body"] = item.get("content", item.get("summary", ""))
        elif "pin" in url:
            content_info["type"] = "pin"

        # 如果搜索没有获取到内容，尝试直接抓取页面
        if not content_info["body"]:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                })
                if resp.status_code == 200:
                    html = resp.text
                    # 简单提取标题
                    title_match = re.search(r"<title>(.*?)</title>", html)
                    if title_match and not content_info["title"]:
                        content_info["title"] = title_match.group(1).replace(" - 知乎", "").strip()
                    # 提取 meta description
                    desc_match = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html)
                    if desc_match and not content_info["summary"]:
                        content_info["summary"] = desc_match.group(1)

    except Exception as e:
        print(f"[zhihu_client] fetch_content_by_url error: {e}")

    return content_info


async def publish_recommendation_pin(title: str, score: float, reason: str, url: str) -> dict | None:
    """
    将推荐成功的内容发布到知乎圈子
    """
    content = f"""🦊 刘看山推荐 | 综合评分 {score:.1f}/10

📄 {title}

💬 推荐理由：{reason}

🔗 原文链接：{url}

#刘看山推荐 #优质内容发现"""

    try:
        result = await publish_pin(content)
        return result
    except Exception as e:
        print(f"[zhihu_client] publish_recommendation_pin error: {e}")
        return None