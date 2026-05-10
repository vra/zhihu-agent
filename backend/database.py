"""数据库初始化与操作"""
import os
import aiosqlite
from config import DATABASE_PATH, WEEKLY_INITIAL_QUOTA, WEEKLY_QUOTA_CAP

# 确保数据目录存在
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zhihu_id TEXT UNIQUE NOT NULL,
    zhihu_name TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    weekly_quota INTEGER DEFAULT 100,
    quota_used INTEGER DEFAULT 0,
    quota_week TEXT DEFAULT '',
    total_submissions INTEGER DEFAULT 0,
    total_recommended INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content_url TEXT NOT NULL,
    content_title TEXT DEFAULT '',
    content_summary TEXT DEFAULT '',
    content_author TEXT DEFAULT '',
    content_type TEXT DEFAULT 'article',
    content_body TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    overall_score REAL DEFAULT 0,
    depth_score REAL DEFAULT 0,
    originality_score REAL DEFAULT 0,
    readability_score REAL DEFAULT 0,
    professionalism_score REAL DEFAULT 0,
    community_score REAL DEFAULT 0,
    ai_detection_score REAL DEFAULT 0,
    review_summary TEXT DEFAULT '',
    improvement_tips TEXT DEFAULT '[]',
    agent_reports TEXT DEFAULT '{}',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content_url TEXT NOT NULL,
    content_title TEXT DEFAULT '',
    overall_score REAL DEFAULT 0,
    recommend_reason TEXT DEFAULT '',
    category TEXT DEFAULT '',
    pin_id TEXT DEFAULT '',
    likes_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS quota_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    change_amount INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    submission_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接"""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """初始化数据库表"""
    db = await get_db()
    try:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    finally:
        await db.close()


# ──────────────────── 用户操作 ────────────────────

async def get_or_create_user(zhihu_id: str, zhihu_name: str = "", avatar_url: str = "") -> dict:
    """获取或创建用户"""
    import datetime
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE zhihu_id = ?", (zhihu_id,))
        row = await cursor.fetchone()
        if row:
            user = dict(row)
            # 检查是否需要重置周额度
            current_week = datetime.datetime.now().strftime("%Y-W%W")
            if user["quota_week"] != current_week:
                await db.execute(
                    "UPDATE users SET weekly_quota = ?, quota_used = 0, quota_week = ? WHERE id = ?",
                    (WEEKLY_INITIAL_QUOTA, current_week, user["id"]),
                )
                await db.commit()
                user["weekly_quota"] = WEEKLY_INITIAL_QUOTA
                user["quota_used"] = 0
                user["quota_week"] = current_week
            return user
        else:
            current_week = datetime.datetime.now().strftime("%Y-W%W")
            await db.execute(
                "INSERT INTO users (zhihu_id, zhihu_name, avatar_url, quota_week) VALUES (?, ?, ?, ?)",
                (zhihu_id, zhihu_name, avatar_url, current_week),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM users WHERE zhihu_id = ?", (zhihu_id,))
            row = await cursor.fetchone()
            return dict(row)
    finally:
        await db.close()


async def update_user_quota(user_id: int, change: int, reason: str, submission_id: int | None = None):
    """更新用户额度"""
    db = await get_db()
    try:
        if change > 0:
            await db.execute(
                "UPDATE users SET weekly_quota = MIN(weekly_quota + ?, ?) WHERE id = ?",
                (change, WEEKLY_INITIAL_QUOTA + WEEKLY_QUOTA_CAP, user_id),
            )
        else:
            await db.execute(
                "UPDATE users SET quota_used = quota_used + ? WHERE id = ?",
                (abs(change), user_id),
            )
        await db.execute(
            "INSERT INTO quota_logs (user_id, change_amount, reason, submission_id) VALUES (?, ?, ?, ?)",
            (user_id, change, reason, submission_id),
        )
        await db.commit()
    finally:
        await db.close()


# ──────────────────── 提交操作 ────────────────────

async def create_submission(user_id: int, content_url: str, content_title: str = "",
                            content_summary: str = "", content_author: str = "",
                            content_type: str = "article", content_body: str = "") -> dict:
    """创建提交记录"""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO submissions
               (user_id, content_url, content_title, content_summary, content_author, content_type, content_body)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, content_url, content_title, content_summary, content_author, content_type, content_body),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM submissions WHERE id = last_insert_rowid()")
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()


async def update_submission_review(submission_id: int, scores: dict, review_summary: str,
                                    improvement_tips: str, agent_reports: str, status: str):
    """更新评审结果"""
    import datetime
    db = await get_db()
    try:
        await db.execute(
            """UPDATE submissions SET
               overall_score = ?, depth_score = ?, originality_score = ?,
               readability_score = ?, professionalism_score = ?, community_score = ?,
               ai_detection_score = ?, review_summary = ?, improvement_tips = ?,
               agent_reports = ?, status = ?, reviewed_at = ?
               WHERE id = ?""",
            (
                scores["overall"], scores["depth"], scores["originality"],
                scores["readability"], scores["professionalism"], scores["community"],
                scores["ai_detection"], review_summary, improvement_tips,
                agent_reports, status, datetime.datetime.now().isoformat(),
                submission_id,
            ),
        )
        await db.execute(
            "UPDATE users SET total_submissions = total_submissions + 1 WHERE id = (SELECT user_id FROM submissions WHERE id = ?)",
            (submission_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def get_submission(submission_id: int) -> dict | None:
    """获取提交记录"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_user_submissions(user_id: int, limit: int = 20) -> list[dict]:
    """获取用户的提交历史"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def check_url_submitted(content_url: str) -> bool:
    """检查 URL 是否已提交过"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM submissions WHERE content_url = ?", (content_url,))
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


# ──────────────────── 推荐榜操作 ────────────────────

async def create_recommendation(submission_id: int, user_id: int, content_url: str,
                                 content_title: str, overall_score: float,
                                 recommend_reason: str, category: str = "") -> dict:
    """创建推荐记录"""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO recommendations
               (submission_id, user_id, content_url, content_title, overall_score, recommend_reason, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (submission_id, user_id, content_url, content_title, overall_score, recommend_reason, category),
        )
        await db.execute(
            "UPDATE users SET total_recommended = total_recommended + 1 WHERE id = ?",
            (user_id,),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM recommendations WHERE id = last_insert_rowid()")
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()


async def get_recommendations(limit: int = 20, category: str = "", sort_by: str = "created_at") -> list[dict]:
    """获取推荐榜列表"""
    db = await get_db()
    try:
        query = "SELECT r.*, s.content_summary, s.depth_score, s.originality_score, s.readability_score, s.professionalism_score, s.community_score, s.ai_detection_score, u.zhihu_name, u.avatar_url FROM recommendations r JOIN submissions s ON r.submission_id = s.id JOIN users u ON r.user_id = u.id"
        params: list = []
        if category:
            query += " WHERE r.category = ?"
            params.append(category)
        if sort_by == "score":
            query += " ORDER BY r.overall_score DESC"
        else:
            query += " ORDER BY r.created_at DESC"
        query += " LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()