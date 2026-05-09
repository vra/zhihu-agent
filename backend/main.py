"""
🦊 刘看山推荐 - 后端服务
AI 驱动的去中心化内容发现平台
"""
import json
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import RECOMMEND_THRESHOLD, HIGH_SCORE_THRESHOLD, RECOMMEND_SUCCESS_BONUS, HIGH_SCORE_BONUS
from database import (
    init_db,
    get_or_create_user,
    update_user_quota,
    create_submission,
    update_submission_review,
    get_submission,
    get_user_submissions,
    check_url_submitted,
    create_recommendation,
    get_recommendations,
)
from review_engine import run_full_review
from zhihu_client import fetch_content_by_url, publish_recommendation_pin, zhihu_search, get_hot_list


# ──────────────────── 应用生命周期 ────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的操作"""
    await init_db()
    print("🦊 刘看山推荐服务已启动！")
    yield
    print("🦊 刘看山推荐服务已关闭。")


app = FastAPI(
    title="🦊 刘看山推荐",
    description="AI 驱动的去中心化内容发现平台",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
liukanshan_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "liukanshan")

if os.path.exists(liukanshan_dir):
    app.mount("/assets/liukanshan", StaticFiles(directory=liukanshan_dir), name="liukanshan")


# ──────────────────── 请求模型 ────────────────────

class SubmitRequest(BaseModel):
    """提交内容评审请求"""
    content_url: str
    zhihu_id: str = "demo_user"
    zhihu_name: str = "演示用户"

class ReviewByTextRequest(BaseModel):
    """直接提交文本评审请求"""
    title: str
    content: str
    zhihu_id: str = "demo_user"
    zhihu_name: str = "演示用户"

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    limit: int = 10


# ──────────────────── API 路由 ────────────────────

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "🦊 刘看山推荐"}


# ──── 用户相关 ────

@app.get("/api/user/{zhihu_id}")
async def get_user_info(zhihu_id: str):
    """获取用户信息和额度"""
    user = await get_or_create_user(zhihu_id)
    remaining_quota = user["weekly_quota"] - user["quota_used"]
    return {
        "user": user,
        "remaining_quota": max(0, remaining_quota),
    }


# ──── 内容提交与评审 ────

@app.post("/api/submit")
async def submit_content(req: SubmitRequest):
    """
    提交知乎内容链接进行评审
    1. 检查额度
    2. 获取内容
    3. 运行多 Agent 评审
    4. 保存结果
    5. 如果推荐成功，发布到圈子
    """
    # 1. 获取/创建用户
    user = await get_or_create_user(req.zhihu_id, req.zhihu_name)
    remaining = user["weekly_quota"] - user["quota_used"]

    if remaining <= 0:
        raise HTTPException(status_code=429, detail="本周推荐额度已用完，请下周再来！")

    # 2. 检查是否重复提交
    if await check_url_submitted(req.content_url):
        raise HTTPException(status_code=400, detail="该内容已经提交过评审了")

    # 3. 获取内容
    content_info = await fetch_content_by_url(req.content_url)
    if not content_info or not content_info.get("title"):
        # 如果无法获取内容，使用 URL 作为标题
        content_info = content_info or {}
        if not content_info.get("title"):
            content_info["title"] = req.content_url
        if not content_info.get("body"):
            content_info["body"] = content_info.get("summary", "")

    # 4. 创建提交记录 & 扣减额度
    submission = await create_submission(
        user_id=user["id"],
        content_url=req.content_url,
        content_title=content_info.get("title", ""),
        content_summary=content_info.get("summary", ""),
        content_author=content_info.get("author", ""),
        content_type=content_info.get("type", "article"),
        content_body=content_info.get("body", ""),
    )
    await update_user_quota(user["id"], -1, "submission", submission["id"])

    # 5. 运行评审
    content_for_review = content_info.get("body", "") or content_info.get("summary", "") or content_info.get("title", "")
    review_result = await run_full_review(
        content_title=content_info.get("title", "未知标题"),
        content_body=content_for_review,
    )

    # 6. 保存评审结果
    await update_submission_review(
        submission_id=submission["id"],
        scores=review_result["scores"],
        review_summary=review_result["review_summary"],
        improvement_tips=json.dumps(review_result["improvement_tips"], ensure_ascii=False),
        agent_reports=json.dumps(review_result["agent_reports"], ensure_ascii=False),
        status=review_result["status"],
    )

    # 7. 如果推荐成功
    if review_result["status"] == "recommended":
        # 创建推荐记录
        rec = await create_recommendation(
            submission_id=submission["id"],
            user_id=user["id"],
            content_url=req.content_url,
            content_title=content_info.get("title", ""),
            overall_score=review_result["scores"]["overall"],
            recommend_reason=review_result["recommend_reason"],
            category=review_result["category"],
        )

        # 奖励额度
        bonus = RECOMMEND_SUCCESS_BONUS
        if review_result["scores"]["overall"] >= HIGH_SCORE_THRESHOLD:
            bonus += HIGH_SCORE_BONUS
        await update_user_quota(user["id"], bonus, "reward", submission["id"])

        # 尝试发布到知乎圈子（非阻塞，失败不影响结果）
        try:
            await publish_recommendation_pin(
                title=content_info.get("title", ""),
                score=review_result["scores"]["overall"],
                reason=review_result["recommend_reason"],
                url=req.content_url,
            )
        except Exception as e:
            print(f"[main] 发布到圈子失败: {e}")

    # 8. 返回结果
    return {
        "submission_id": submission["id"],
        "status": review_result["status"],
        "scores": review_result["scores"],
        "review_summary": review_result["review_summary"],
        "improvement_tips": review_result["improvement_tips"],
        "recommend_reason": review_result["recommend_reason"],
        "category": review_result["category"],
        "agent_reports": review_result["agent_reports"],
    }


@app.post("/api/review-text")
async def review_text_content(req: ReviewByTextRequest):
    """
    直接提交文本进行评审（Demo 用，不需要知乎链接）
    """
    user = await get_or_create_user(req.zhihu_id, req.zhihu_name)
    remaining = user["weekly_quota"] - user["quota_used"]

    if remaining <= 0:
        raise HTTPException(status_code=429, detail="本周推荐额度已用完，请下周再来！")

    # 创建提交记录
    submission = await create_submission(
        user_id=user["id"],
        content_url=f"text://{req.title}",
        content_title=req.title,
        content_summary=req.content[:200],
        content_author=req.zhihu_name,
        content_type="text",
        content_body=req.content,
    )
    await update_user_quota(user["id"], -1, "submission", submission["id"])

    # 运行评审
    review_result = await run_full_review(
        content_title=req.title,
        content_body=req.content,
    )

    # 保存评审结果
    await update_submission_review(
        submission_id=submission["id"],
        scores=review_result["scores"],
        review_summary=review_result["review_summary"],
        improvement_tips=json.dumps(review_result["improvement_tips"], ensure_ascii=False),
        agent_reports=json.dumps(review_result["agent_reports"], ensure_ascii=False),
        status=review_result["status"],
    )

    # 如果推荐成功
    if review_result["status"] == "recommended":
        await create_recommendation(
            submission_id=submission["id"],
            user_id=user["id"],
            content_url=f"text://{req.title}",
            content_title=req.title,
            overall_score=review_result["scores"]["overall"],
            recommend_reason=review_result["recommend_reason"],
            category=review_result["category"],
        )
        bonus = RECOMMEND_SUCCESS_BONUS
        if review_result["scores"]["overall"] >= HIGH_SCORE_THRESHOLD:
            bonus += HIGH_SCORE_BONUS
        await update_user_quota(user["id"], bonus, "reward", submission["id"])

    return {
        "submission_id": submission["id"],
        "status": review_result["status"],
        "scores": review_result["scores"],
        "review_summary": review_result["review_summary"],
        "improvement_tips": review_result["improvement_tips"],
        "recommend_reason": review_result["recommend_reason"],
        "category": review_result["category"],
        "agent_reports": review_result["agent_reports"],
    }


# ──── 评审报告 ────

@app.get("/api/submission/{submission_id}")
async def get_submission_detail(submission_id: int):
    """获取评审报告详情"""
    submission = await get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="评审记录不存在")

    # 解析 JSON 字段
    try:
        submission["improvement_tips"] = json.loads(submission.get("improvement_tips", "[]"))
    except (json.JSONDecodeError, TypeError):
        submission["improvement_tips"] = []
    try:
        submission["agent_reports"] = json.loads(submission.get("agent_reports", "{}"))
    except (json.JSONDecodeError, TypeError):
        submission["agent_reports"] = {}

    return submission


@app.get("/api/user/{zhihu_id}/submissions")
async def get_user_history(zhihu_id: str):
    """获取用户评审历史"""
    user = await get_or_create_user(zhihu_id)
    submissions = await get_user_submissions(user["id"])
    for s in submissions:
        try:
            s["improvement_tips"] = json.loads(s.get("improvement_tips", "[]"))
        except (json.JSONDecodeError, TypeError):
            s["improvement_tips"] = []
        try:
            s["agent_reports"] = json.loads(s.get("agent_reports", "{}"))
        except (json.JSONDecodeError, TypeError):
            s["agent_reports"] = {}
    return {"submissions": submissions}


# ──── 推荐榜 ────

@app.get("/api/recommendations")
async def list_recommendations(limit: int = 20, category: str = "", sort: str = "created_at"):
    """获取刘看山推荐榜"""
    recs = await get_recommendations(limit=limit, category=category, sort_by=sort)
    return {"recommendations": recs}


# ──── 知乎 API 代理 ────

@app.get("/api/zhihu/hot")
async def proxy_hot_list():
    """获取知乎热榜"""
    try:
        result = await get_hot_list()
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取热榜失败: {str(e)}")


@app.post("/api/zhihu/search")
async def proxy_search(req: SearchRequest):
    """知乎搜索"""
    try:
        result = await zhihu_search(req.query, req.limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"搜索失败: {str(e)}")


# ──── 前端页面服务 ────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """服务前端页面"""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    # 如果前端还没构建，返回一个简单的提示页面
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head><title>🦊 刘看山推荐</title></head>
    <body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;">
        <div style="text-align:center;">
            <h1>🦊 刘看山推荐</h1>
            <p>后端服务已启动！前端页面构建中...</p>
            <p>API 文档: <a href="/docs">/docs</a></p>
        </div>
    </body>
    </html>
    """)


# ──────────────────── 启动入口 ────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)