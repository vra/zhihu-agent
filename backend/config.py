"""应用配置"""
import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# 知乎 API 配置
ZHIHU_TOKEN = os.getenv("zhihu_token", "")
ZHIHU_SK = os.getenv("sk", "")
ZHIHU_API_BASE = "https://api.zhihu.com"
ZHIHU_RING_API_BASE = "https://www.zhihu.com/ring/moltbook/api"

# OpenAI 配置（用于多 Agent 评审）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 知乎直答 Agent 配置
ZHIHU_AGENT_API = "https://api.zhihu.com/v1/chat/completions"

# 数据库
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "liukanshan.db")

# 额度配置
WEEKLY_INITIAL_QUOTA = 3       # 每周初始额度
RECOMMEND_SUCCESS_BONUS = 2    # 推荐成功奖励额度
HIGH_SCORE_BONUS = 3           # 高分（≥9.0）额外奖励
WEEKLY_QUOTA_CAP = 15          # 单周额度上限
LOW_SCORE_THRESHOLD = 5.0      # 低分阈值
RECOMMEND_THRESHOLD = 7.0      # 推荐成功阈值
HIGH_SCORE_THRESHOLD = 9.0     # 高分阈值

# 评审 Agent 权重
AGENT_WEIGHTS = {
    "depth": 0.20,         # 内容深度
    "originality": 0.20,   # 原创性
    "readability": 0.15,   # 可读性
    "professionalism": 0.15,  # 专业度
    "community": 0.15,     # 社区价值
    "ai_detection": 0.15,  # 人类原创度
}