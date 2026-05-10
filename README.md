# 刘看山推荐 — AI 驱动的去中心化内容发现平台

> 让优质内容被看见，让每一个认真创作的人都不被埋没。

Web: https://zhihu-agent.zh-cn.edgeone.cool/

## 项目简介

「刘看山推荐」是一个基于多 AI Agent 评审机制的去中心化内容推荐系统。它让知乎吉祥物刘看山化身为"内容伯乐"，通过内容质量本身（而非粉丝数）决定曝光，帮助优质新人内容破圈。

**参赛赛道**：知乎 Hackathon | AI 脑洞实验室
- 主赛道：「引力场」—— 聚焦社区社交与内容分发
- 副赛道：「刘看山」—— IP 智能新生计划

## 核心理念

> 在知乎，你的内容值多少分，不该由你有多少粉丝决定，而该由你写了什么决定。

## 产品亮点

- **多 Agent 评审**：6 位刘看山 AI 评审员从不同角度独立打分，综合得出最终评分，避免单一偏见
- **AI 内容鉴别**：内置 AI 生成内容检测，鼓励人类原创表达
- **去中心化推荐**：纯内容质量导向，0 粉丝新人和百万粉丝大V享有平等评审机会
- **额度博弈机制**：有限额度让用户只提交最好的内容，好内容获得更多额度奖励
- **刘看山 IP 融合**：刘看山不只是 logo，而是整个产品的核心人格

## 评审团介绍

| 评审员 | 角色 | 评审维度 | 权重 |
|--------|------|----------|------|
| 学术山 | 严谨的学者 | 内容深度：论证是否充分、逻辑是否自洽 | 20% |
| 阅读山 | 挑剔的读者 | 可读性：结构是否清晰、表达是否流畅 | 15% |
| 创意山 | 追求新意的创意人 | 原创性：观点是否独特、非搬运/洗稿 | 20% |
| 社区山 | 资深知乎用户 | 社区价值：是否能引发有价值的讨论 | 15% |
| 鉴真山 | AI 内容鉴别专家 | 人类原创度：检测是否为 AI 生成内容 | 15% |
| 专业度 | 综合判断 | 专业度：引用准确、术语规范、数据可靠 | 15% |

## 技术架构

```
┌─────────────────────────────────────────────┐
│              前端 (单页面应用)                │
│         HTML + CSS + JavaScript              │
└──────────────────┬──────────────────────────┘
                   │ HTTP API
┌──────────────────▼──────────────────────────┐
│            后端 (FastAPI)                     │
│                                              │
│  ┌────────────┐  ┌────────────┐             │
│  │ 知乎 API   │  │ 多Agent    │             │
│  │ 客户端     │  │ 评审引擎   │             │
│  └────────────┘  └────────────┘             │
│  ┌────────────┐  ┌────────────┐             │
│  │ SQLite     │  │ LLM API   │             │
│  │ 数据库     │  │ (OpenAI)  │             │
│  └────────────┘  └────────────┘             │
└─────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | HTML + CSS + JS | 单页面应用，无需构建工具 |
| 后端 | Python FastAPI | 异步高性能，AI 生态丰富 |
| 数据库 | SQLite | 轻量，无需额外部署 |
| AI 评审 | OpenAI API | 多 Agent 并行评审 |
| 知乎 API | HMAC-SHA256 签名认证 | 内容获取 + 圈子发布 |
| 部署 | Docker + EdgeOne Pages | 容器化部署 |

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 1. 克隆项目

```bash
git clone https://github.com/vra/zhihu-agent.git
cd zhihu-agent
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥
```

`.env` 文件需要包含：

```
zhihu_token=your-zhihu-token
sk=your-secret-key
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### 3. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 4. 启动服务

```bash
# 方式一：使用部署脚本
./deploy.sh dev

# 方式二：手动启动
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问

- 前端页面：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 部署

### Docker 部署

```bash
# 构建镜像
./deploy.sh docker-build

# 运行容器
./deploy.sh docker-run

# 查看日志
./deploy.sh docker-logs

# 停止容器
./deploy.sh docker-stop
```

### EdgeOne Pages 部署（前端）

```bash
# 配置后端地址并准备部署文件
BACKEND_URL=https://your-backend.com ./deploy.sh edgeone-setup

# 部署到 EdgeOne Pages
./deploy.sh edgeone
```

### 完整部署

```bash
./deploy.sh full
```

### 查看服务状态

```bash
./deploy.sh status
```

## 项目结构

```
zhihu-agent/
├── backend/                 # 后端代码
│   ├── main.py             # FastAPI 主应用
│   ├── config.py           # 配置管理
│   ├── database.py         # 数据库操作
│   ├── review_engine.py    # 多 Agent 评审引擎
│   ├── zhihu_client.py     # 知乎 API 客户端
│   └── requirements.txt    # Python 依赖
├── frontend/               # 前端代码
│   └── index.html          # 单页面应用
├── docs/                   # 文档
│   └── product-plan.md     # 产品方案
├── liukanshan/             # 刘看山素材
├── .env.example            # 环境变量示例
├── Dockerfile              # Docker 构建文件
├── deploy.sh               # 部署脚本
├── edgeone.json            # EdgeOne Pages 配置
└── README.md               # 项目说明
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/user/{zhihu_id}` | GET | 获取用户信息和额度 |
| `/api/submit` | POST | 提交知乎链接评审 |
| `/api/review-text` | POST | 直接提交文本评审 |
| `/api/submission/{id}` | GET | 获取评审报告详情 |
| `/api/user/{zhihu_id}/submissions` | GET | 获取用户评审历史 |
| `/api/recommendations` | GET | 获取推荐榜 |
| `/api/zhihu/hot` | GET | 获取知乎热榜 |
| `/api/zhihu/search` | POST | 知乎搜索 |

## 评分机制

- 每个 Agent 独立打分（1-10 分）
- 加权计算综合得分（满分 10 分）
- 综合得分 >= 7.0 分：推荐成功，进入「刘看山推荐榜」
- 综合得分 5.0 - 6.9 分：给出改进建议，不推荐
- 综合得分 < 5.0 分：未通过评审

## 额度规则

| 规则 | 说明 |
|------|------|
| 初始额度 | 每周 3 次推荐申请额度 |
| 推荐成功奖励 | 每次推荐成功（>= 7.0 分）+2 次额度 |
| 高分奖励 | 评分 >= 9.0 分额外 +3 次额度 |
| 额度上限 | 单周最多 15 次 |

## License

MIT
