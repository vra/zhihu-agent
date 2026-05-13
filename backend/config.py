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

# OAuth 配置
ZHIHU_OAUTH_APP_ID = os.getenv("ZHIHU_OAUTH_APP_ID", "")
ZHIHU_OAUTH_APP_KEY = os.getenv("ZHIHU_OAUTH_APP_KEY", "")
ZHIHU_OAUTH_REDIRECT_URI = os.getenv("ZHIHU_OAUTH_REDIRECT_URI", "https://zhihu-agent-zvfeta9n6c.zh-cn.edgeone.cool/")

# OpenAI 配置（用于多 Agent 评审）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 知乎直答 Agent 配置
ZHIHU_AGENT_API = "https://api.zhihu.com/v1/chat/completions"

# 数据库
if os.getenv("VERCEL"):
    DATABASE_PATH = "/tmp/liukanshan.db"
else:
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "liukanshan.db")

# 额度配置（动态额度基准值）
MONTHLY_BASE_QUOTA = 100        # 最高月额度（新人基准，调试模式可设高）
RECOMMEND_SUCCESS_BONUS = 2     # 推荐成功奖励额度
HIGH_SCORE_BONUS = 3            # 高分（≥9.0）额外奖励
MONTHLY_QUOTA_CAP = 15          # 单月额度上限
LOW_SCORE_THRESHOLD = 5.0       # 低分阈值
RECOMMEND_THRESHOLD = 7.0       # 推荐成功阈值
HIGH_SCORE_THRESHOLD = 9.0      # 高分阈值

# ── 用户等级与徽章系统（动态额度） ──
# 核心设计：新人获得更多推荐次数，随粉丝数/赞同数/等级提升逐步降低
# 等级由粉丝数和赞同数共同决定，取较高者对应的等级
# 等级越高 → 月额度越低，鼓励新人创作，老手靠质量取胜

FOLLOWER_THRESHOLDS = [0, 100, 500, 2000, 10000, 50000, 200000]
UPVOTE_THRESHOLDS = [0, 500, 2000, 10000, 50000, 200000, 1000000]

# 每个等级的基础月额度（新人最高 100，传奇最低 5）
LEVEL_QUOTAS = [100, 35, 25, 18, 12, 8, 5]

# 等级徽章名称（刘看山主题，从萌新到传奇）
BADGE_NAMES = [
    "看山小萌新",    # Lv0: 纯新人，什么都不懂但充满热情
    "初识看山",      # Lv1: 刚开始在知乎积累
    "看山常客",      # Lv2: 有一定社区基础
    "看山达人",      # Lv3: 活跃创作者
    "看山鉴赏家",    # Lv4: 内容质量有口碑
    "看山引航员",    # Lv5: 社区意见领袖
    "看山传奇",      # Lv6: 顶级创作者
]

# 兼容旧代码的别名
WEEKLY_INITIAL_QUOTA = MONTHLY_BASE_QUOTA
WEEKLY_QUOTA_CAP = MONTHLY_QUOTA_CAP

# 评审 Agent 权重
AGENT_WEIGHTS = {
    "depth": 0.20,         # 内容深度
    "originality": 0.20,   # 原创性
    "readability": 0.15,   # 可读性
    "professionalism": 0.15,  # 专业度
    "community": 0.15,     # 社区价值
    "ai_detection": 0.15,  # 人类原创度
}

# 内容分类及评审侧重点
CONTENT_CATEGORIES = {
    "科技": {
        "description": "技术、编程、AI、互联网、硬件等",
        "emphasis": "侧重专业度和技术深度。论据是否有代码/数据支撑，术语是否准确，技术原理是否讲解清晰。",
    },
    "人文": {
        "description": "文学、历史、哲学、艺术、社会学等",
        "emphasis": "侧重原创性和可读性。观点是否独到，论证是否有文献支撑，文字表达是否优美有感染力。",
    },
    "生活": {
        "description": "美食、旅行、家居、宠物、日常分享等",
        "emphasis": "侧重真实性和社区价值。是否有真实体验细节，是否对他人有实际帮助和参考价值。",
    },
    "职场": {
        "description": "求职、管理、创业、行业分析等",
        "emphasis": "侧重实用性和案例支撑。是否有具体案例/数据，建议是否可操作，是否避免空洞鸡汤。",
    },
    "教育": {
        "description": "学习方法、考试、学术、育儿等",
        "emphasis": "侧重结构清晰和科学性。知识是否准确，方法是否有依据，逻辑是否层层递进。",
    },
    "财经": {
        "description": "投资、经济、商业模式、理财等",
        "emphasis": "侧重数据支撑和专业度。是否有财务数据/图表佐证，分析是否客观避免误导。",
    },
    "健康": {
        "description": "医学、心理、运动、养生等",
        "emphasis": "侧重循证和专业度。是否引用可靠研究/指南，是否区分了个人经验和科学结论。",
    },
    "娱乐": {
        "description": "影视、游戏、音乐、动漫等",
        "emphasis": "侧重原创性和社区价值。评论/分析是否有独到视角，是否能引发有趣讨论。",
    },
}