"""数据库初始化与操作"""
import os
import aiosqlite
from config import (
    DATABASE_PATH, WEEKLY_INITIAL_QUOTA, WEEKLY_QUOTA_CAP,
    FOLLOWER_THRESHOLDS, UPVOTE_THRESHOLDS, LEVEL_QUOTAS, BADGE_NAMES,
)

# 确保数据目录存在
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zhihu_id TEXT UNIQUE NOT NULL,
    zhihu_name TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    monthly_quota INTEGER DEFAULT 100,
    quota_used INTEGER DEFAULT 0,
    quota_month TEXT DEFAULT '',
    total_submissions INTEGER DEFAULT 0,
    total_recommended INTEGER DEFAULT 0,
    followers_count INTEGER DEFAULT 0,
    upvotes_count INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    badge TEXT DEFAULT '看山小萌新',
    url_token TEXT DEFAULT '',
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

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zhihu_id TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def calculate_user_level(followers: int, upvotes: int) -> tuple[int, str, int]:
    """根据粉丝数和赞同数计算用户等级、徽章和周额度
    
    核心规则：新手获得更多推荐次数，名气越大额度越低
    - 分别用粉丝数和赞同数查阈值表，取较高等级
    - 等级 0 (萌新) 每周 100 次，等级 6 (传奇) 每周 5 次
    """
    follower_level = 0
    for i in range(len(FOLLOWER_THRESHOLDS)):
        if followers >= FOLLOWER_THRESHOLDS[i]:
            follower_level = i

    upvote_level = 0
    for i in range(len(UPVOTE_THRESHOLDS)):
        if upvotes >= UPVOTE_THRESHOLDS[i]:
            upvote_level = i

    level = max(follower_level, upvote_level)
    level = min(level, len(BADGE_NAMES) - 1)

    badge = BADGE_NAMES[level]
    quota = LEVEL_QUOTAS[level]

    return level, badge, quota


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
        # 迁移: 为已有的 users 表添加 url_token 列
        try:
            await db.execute("ALTER TABLE users ADD COLUMN url_token TEXT DEFAULT ''")
        except Exception:
            pass  # 列已存在
        await db.commit()
    finally:
        await db.close()


# ──────────────────── 用户操作 ────────────────────

async def get_or_create_user(zhihu_id: str, zhihu_name: str = "", avatar_url: str = "",
                             followers_count: int = 0, upvotes_count: int = 0) -> dict:
    """获取或创建用户，自动计算等级与动态额度"""
    import datetime
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE zhihu_id = ?", (zhihu_id,))
        row = await cursor.fetchone()
        current_month = datetime.datetime.now().strftime("%Y-%m")

        if row:
            user = dict(row)
            needs_update = False

            # 如果传入了新的社交数据且与已有数据不同，更新
            if followers_count > 0 and followers_count != user.get("followers_count", 0):
                user["followers_count"] = followers_count
                needs_update = True
            if upvotes_count > 0 and upvotes_count != user.get("upvotes_count", 0):
                user["upvotes_count"] = upvotes_count
                needs_update = True

            if needs_update:
                new_level, new_badge, new_quota = calculate_user_level(
                    user["followers_count"] or 0,
                    user["upvotes_count"] or 0,
                )
                user["level"] = new_level
                user["badge"] = new_badge

            # 检查是否需要重置月额度
            if user["quota_month"] != current_month:
                _, _, new_quota = calculate_user_level(
                    user.get("followers_count", 0) or 0,
                    user.get("upvotes_count", 0) or 0,
                )
                await db.execute(
                    "UPDATE users SET monthly_quota = ?, quota_used = 0, quota_month = ?, followers_count = ?, upvotes_count = ?, level = ?, badge = ? WHERE id = ?",
                    (new_quota, current_month, user.get("followers_count", 0) or 0,
                     user.get("upvotes_count", 0) or 0, user["level"], user["badge"], user["id"]),
                )
                await db.commit()
                user["monthly_quota"] = new_quota
                user["quota_used"] = 0
                user["quota_month"] = current_month
            elif needs_update:
                await db.execute(
                    "UPDATE users SET followers_count = ?, upvotes_count = ?, level = ?, badge = ? WHERE id = ?",
                    (user["followers_count"], user["upvotes_count"], user["level"], user["badge"], user["id"]),
                )
                await db.commit()
            return user
        else:
            level, badge, quota = calculate_user_level(followers_count, upvotes_count)
            await db.execute(
                "INSERT INTO users (zhihu_id, zhihu_name, avatar_url, followers_count, upvotes_count, level, badge, monthly_quota, quota_month) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (zhihu_id, zhihu_name, avatar_url, followers_count, upvotes_count, level, badge, quota, current_month),
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
                "UPDATE users SET monthly_quota = MIN(monthly_quota + ?, ?) WHERE id = ?",
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


async def update_user_social_stats(zhihu_id: str, followers_count: int = 0, upvotes_count: int = 0) -> dict:
    """更新用户社交数据并重新计算等级和额度"""
    import datetime
    db = await get_db()
    try:
        user = await get_or_create_user(zhihu_id, followers_count=followers_count, upvotes_count=upvotes_count)
        return user
    finally:
        await db.close()


async def update_user_url_token(zhihu_id: str, url_token: str) -> None:
    """更新用户的知乎 URL slug"""
    db = await get_db()
    try:
        await db.execute("UPDATE users SET url_token = ? WHERE zhihu_id = ?", (url_token, zhihu_id))
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


# ──────────────────── OAuth Token 管理 ────────────────────

async def save_oauth_token(zhihu_id: str, access_token: str, expires_in: int) -> None:
    """保存或更新 OAuth token"""
    import datetime
    db = await get_db()
    try:
        expires_at = (datetime.datetime.now() + datetime.timedelta(seconds=expires_in)).isoformat()
        await db.execute(
            """INSERT INTO oauth_tokens (zhihu_id, access_token, expires_at)
               VALUES (?, ?, ?)
               ON CONFLICT(zhihu_id) DO UPDATE SET
               access_token = excluded.access_token,
               expires_at = excluded.expires_at,
               created_at = CURRENT_TIMESTAMP""",
            (zhihu_id, access_token, expires_at),
        )
        await db.commit()
    finally:
        await db.close()


async def get_valid_token(zhihu_id: str) -> str | None:
    """获取有效的 OAuth token，过期则返回 None"""
    import datetime
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT access_token, expires_at FROM oauth_tokens WHERE zhihu_id = ?",
            (zhihu_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        token_data = dict(row)
        expires_at = datetime.datetime.fromisoformat(token_data["expires_at"])
        if datetime.datetime.now() >= expires_at:
            return None
        return token_data["access_token"]
    finally:
        await db.close()


async def delete_expired_tokens() -> None:
    """清理过期的 OAuth token"""
    import datetime
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM oauth_tokens WHERE expires_at < ?",
            (datetime.datetime.now().isoformat(),),
        )
        await db.commit()
    finally:
        await db.close()