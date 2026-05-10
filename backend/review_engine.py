"""
多 Agent 评审引擎
5 个 Agent 独立评审 + 刘看山汇总
"""
import os
import json
import asyncio

# 清除代理环境变量，避免 SOCKS 代理导致请求失败
for _proxy_var in [
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
]:
    os.environ.pop(_proxy_var, None)

from openai import AsyncOpenAI
from config import (
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    AGENT_WEIGHTS, RECOMMEND_THRESHOLD, HIGH_SCORE_THRESHOLD,
)

# 初始化 OpenAI 客户端
llm = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# ──────────────────── Agent 人设定义 ────────────────────

AGENTS = {
    "depth": {
        "name": "🎓 学术山",
        "role": "严谨的学者",
        "system_prompt": """你是「学术山」，刘看山评审团中的学术派成员。你是一位严谨的学者，专注于评估内容的深度和逻辑性。

你的评审维度是【内容深度】，请从以下角度评分（1-10分）：
1. 论证是否充分：观点是否有足够的论据支撑
2. 逻辑是否自洽：推理过程是否严密，有无逻辑漏洞
3. 是否有独到见解：是否提出了新颖的观点或角度
4. 分析深度：是否深入问题本质，而非浮于表面
5. 知识广度：是否展现了跨领域的知识储备

请严格按照以下 JSON 格式输出，不要输出其他内容：
{
  "score": 8.5,
  "comment": "一句话点评（50字以内）",
  "details": "详细评审意见（100-200字）"
}""",
    },
    "readability": {
        "name": "📖 阅读山",
        "role": "挑剔的读者",
        "system_prompt": """你是「阅读山」，刘看山评审团中的读者派成员。你是一位挑剔的读者，专注于评估内容的可读性和阅读体验。

你的评审维度是【可读性】，请从以下角度评分（1-10分）：
1. 结构清晰度：文章结构是否合理，段落划分是否得当
2. 表达流畅度：语言是否通顺，用词是否准确
3. 排版友好度：是否使用了合理的标题、列表、分段等
4. 开头吸引力：开头是否能吸引读者继续阅读
5. 信息密度：是否做到了言之有物，没有过多废话

请严格按照以下 JSON 格式输出，不要输出其他内容：
{
  "score": 8.5,
  "comment": "一句话点评（50字以内）",
  "details": "详细评审意见（100-200字）"
}""",
    },
    "originality": {
        "name": "💡 创意山",
        "role": "追求新意的创意人",
        "system_prompt": """你是「创意山」，刘看山评审团中的原创派成员。你追求新意，厌恶陈词滥调，专注于评估内容的原创性。

你的评审维度是【原创性】，请从以下角度评分（1-10分）：
1. 观点独特性：是否提出了与众不同的观点或视角
2. 内容新颖度：是否包含新的信息、数据或案例
3. 非搬运/洗稿：内容是否为原创，而非简单搬运或改写
4. 创意表达：是否用了创新的表达方式或叙事手法
5. 思考独立性：是否体现了独立思考，而非人云亦云

请严格按照以下 JSON 格式输出，不要输出其他内容：
{
  "score": 8.5,
  "comment": "一句话点评（50字以内）",
  "details": "详细评审意见（100-200字）"
}""",
    },
    "community": {
        "name": "🤝 社区山",
        "role": "资深知乎用户",
        "system_prompt": """你是「社区山」，刘看山评审团中的社区派成员。你是一位资深知乎用户，了解社区文化，专注于评估内容的社区价值。

你的评审维度是【社区价值】，请从以下角度评分（1-10分）：
1. 讨论价值：是否能引发有价值的讨论和思考
2. 帮助他人：是否对其他用户有实际帮助
3. 知识贡献：是否为社区贡献了有价值的知识
4. 互动潜力：是否容易引起共鸣和互动
5. 社区适配：是否符合知乎社区的调性和氛围

请严格按照以下 JSON 格式输出，不要输出其他内容：
{
  "score": 8.5,
  "comment": "一句话点评（50字以内）",
  "details": "详细评审意见（100-200字）"
}""",
    },
    "ai_detection": {
        "name": "🔍 鉴真山",
        "role": "AI 内容鉴别专家",
        "system_prompt": """你是「鉴真山」，刘看山评审团中的 AI 内容鉴别专家。你专门负责检测内容是否由 AI 生成。

你的评审维度是【人类原创度】，请从以下角度评分（1-10分，分数越高表示越像人类写的）：
1. 语言模式：是否存在 AI 典型的表达模式（如过度使用"首先/其次/最后"、"总的来说"、"值得注意的是"等连接词）
2. 个人经验：是否包含真实的个人经历、具体细节、情感表达
3. 创意独特性：是否存在 AI 常见的"正确但无趣"的表达方式
4. 结构模式：是否存在 AI 生成内容的典型结构（如过于工整的并列结构、每段长度相近）
5. 语言自然度：是否有口语化表达、个人风格、幽默感等人类特征

评分标准：
- 9-10分：明显的人类创作特征，有个人风格和真实经历
- 7-8分：基本原创，可能使用 AI 辅助润色，但核心观点为原创
- 4-6分：较多 AI 生成痕迹，但有人工编辑
- 1-3分：大量 AI 生成特征，缺乏人类创作痕迹

请严格按照以下 JSON 格式输出，不要输出其他内容：
{
  "score": 8.5,
  "comment": "一句话点评（50字以内）",
  "details": "详细评审意见（100-200字）"
}""",
    },
}

# ──────────────────── 单 Agent 评审 ────────────────────

async def run_single_agent(agent_key: str, content_title: str, content_body: str) -> dict:
    """运行单个 Agent 评审"""
    agent = AGENTS[agent_key]
    user_message = f"""请评审以下知乎内容：

【标题】{content_title}

【正文】
{content_body[:3000]}
"""
    try:
        response = await llm.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": agent["system_prompt"]},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        result_text = response.choices[0].message.content.strip()

        # 解析 JSON
        # 处理可能的 markdown 代码块包裹
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        result = json.loads(result_text)
        return {
            "agent": agent_key,
            "name": agent["name"],
            "score": float(result.get("score", 5.0)),
            "comment": result.get("comment", ""),
            "details": result.get("details", ""),
        }
    except Exception as e:
        print(f"[review_engine] Agent {agent_key} error: {e}")
        return {
            "agent": agent_key,
            "name": agent["name"],
            "score": 5.0,
            "comment": "评审过程中出现异常",
            "details": f"评审异常: {str(e)}",
        }


# ──────────────────── 专业度评估（综合判断） ────────────────────

async def evaluate_professionalism(content_title: str, content_body: str) -> dict:
    """专业度评估 - 由综合 prompt 判断"""
    system_prompt = """你是一位专业度评审专家，负责评估内容的专业水平。

你的评审维度是【专业度】，请从以下角度评分（1-10分）：
1. 引用准确性：引用的数据、文献、案例是否准确
2. 术语使用：专业术语使用是否正确
3. 事实核查：陈述的事实是否可靠
4. 方法论：分析方法是否科学合理
5. 领域理解：是否展现了对该领域的深入理解

请严格按照以下 JSON 格式输出，不要输出其他内容：
{
  "score": 8.5,
  "comment": "一句话点评（50字以内）",
  "details": "详细评审意见（100-200字）"
}"""

    user_message = f"""请评审以下知乎内容的专业度：

【标题】{content_title}

【正文】
{content_body[:3000]}
"""
    try:
        response = await llm.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        result = json.loads(result_text)
        return {
            "agent": "professionalism",
            "name": "🎯 专业度",
            "score": float(result.get("score", 5.0)),
            "comment": result.get("comment", ""),
            "details": result.get("details", ""),
        }
    except Exception as e:
        print(f"[review_engine] professionalism error: {e}")
        return {
            "agent": "professionalism",
            "name": "🎯 专业度",
            "score": 5.0,
            "comment": "评审过程中出现异常",
            "details": f"评审异常: {str(e)}",
        }


# ──────────────────── 刘看山汇总 ────────────────────

async def generate_summary(content_title: str, agent_results: list[dict], overall_score: float) -> dict:
    """刘看山汇总评语和改进建议"""
    # 构建评审摘要
    reviews_text = "\n".join([
        f"- {r['name']}（{r['score']:.1f}分）：{r['comment']}"
        for r in agent_results
    ])

    if overall_score >= RECOMMEND_THRESHOLD:
        status = "推荐成功 🏆"
    else:
        status = "暂未推荐 📝"

    system_prompt = """你是「刘看山」，知乎的官方吉祥物，也是内容评审团的团长。
你性格温暖、有趣、鼓励创作，但也会诚恳地指出不足。
请根据各位评审员的评审结果，生成：
1. 一段综合评语（以刘看山的口吻，150字左右，温暖但专业）
2. 3条具体可操作的改进建议
3. 一句推荐理由（如果推荐成功的话，30字以内）
4. 内容分类（从以下选择一个：科技、人文、生活、职场、教育、财经、健康、娱乐、其他）

请严格按照以下 JSON 格式输出：
{
  "summary": "综合评语",
  "tips": ["建议1", "建议2", "建议3"],
  "recommend_reason": "推荐理由",
  "category": "分类"
}"""

    user_message = f"""内容标题：{content_title}
综合评分：{overall_score:.1f}/10
评审状态：{status}

各评审员评审结果：
{reviews_text}
"""
    try:
        response = await llm.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        return json.loads(result_text)
    except Exception as e:
        print(f"[review_engine] summary error: {e}")
        return {
            "summary": f"综合评分 {overall_score:.1f} 分。感谢你的创作！",
            "tips": ["继续保持创作热情", "可以尝试更深入的分析", "注意文章结构的优化"],
            "recommend_reason": "值得一读的内容",
            "category": "其他",
        }


# ──────────────────── 完整评审流程 ────────────────────

async def run_full_review(content_title: str, content_body: str) -> dict:
    """
    运行完整的多 Agent 评审流程
    返回完整的评审结果
    """
    # 1. 并行运行 5 个 Agent + 专业度评估
    tasks = [
        run_single_agent("depth", content_title, content_body),
        run_single_agent("readability", content_title, content_body),
        run_single_agent("originality", content_title, content_body),
        run_single_agent("community", content_title, content_body),
        run_single_agent("ai_detection", content_title, content_body),
        evaluate_professionalism(content_title, content_body),
    ]
    agent_results = await asyncio.gather(*tasks)

    # 2. 计算加权综合得分
    scores = {}
    for result in agent_results:
        key = result["agent"]
        scores[key] = result["score"]

    overall_score = (
        scores.get("depth", 5) * AGENT_WEIGHTS["depth"]
        + scores.get("originality", 5) * AGENT_WEIGHTS["originality"]
        + scores.get("readability", 5) * AGENT_WEIGHTS["readability"]
        + scores.get("professionalism", 5) * AGENT_WEIGHTS["professionalism"]
        + scores.get("community", 5) * AGENT_WEIGHTS["community"]
        + scores.get("ai_detection", 5) * AGENT_WEIGHTS["ai_detection"]
    )
    overall_score = round(overall_score, 1)

    # 3. 刘看山汇总
    summary_result = await generate_summary(content_title, agent_results, overall_score)

    # 4. 判定状态
    if overall_score >= RECOMMEND_THRESHOLD:
        status = "recommended"
    else:
        status = "rejected"

    # 5. 组装结果
    return {
        "scores": {
            "overall": overall_score,
            "depth": scores.get("depth", 5),
            "originality": scores.get("originality", 5),
            "readability": scores.get("readability", 5),
            "professionalism": scores.get("professionalism", 5),
            "community": scores.get("community", 5),
            "ai_detection": scores.get("ai_detection", 5),
        },
        "status": status,
        "review_summary": summary_result.get("summary", ""),
        "improvement_tips": summary_result.get("tips", []),
        "recommend_reason": summary_result.get("recommend_reason", ""),
        "category": summary_result.get("category", "其他"),
        "agent_reports": {r["agent"]: {
            "name": r["name"],
            "score": r["score"],
            "comment": r["comment"],
            "details": r["details"],
        } for r in agent_results},
    }