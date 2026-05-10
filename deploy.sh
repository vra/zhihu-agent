#!/bin/bash
# ============================================================
# 刘看山推荐 — 一键部署脚本
# 支持: EdgeOne Pages (前端) + Docker (后端)
# ============================================================
set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="liukanshan-recommend"
CONTAINER_NAME="liukanshan-recommend"
PORT="${PORT:-8000}"

# ============================================================
# 用法
# ============================================================
usage() {
    echo ""
    echo "刘看山推荐 — 部署脚本"
    echo ""
    echo "用法: ./deploy.sh <command>"
    echo ""
    echo "命令:"
    echo "  dev           本地开发模式（启动后端 + 前端预览）"
    echo "  docker-build  构建 Docker 镜像"
    echo "  docker-run    运行 Docker 容器"
    echo "  docker-stop   停止 Docker 容器"
    echo "  docker-logs   查看 Docker 日志"
    echo "  edgeone       部署前端到 EdgeOne Pages"
    echo "  full          完整部署（Docker 后端 + EdgeOne 前端）"
    echo "  status        查看服务状态"
    echo ""
}

# ============================================================
# 本地开发
# ============================================================
cmd_dev() {
    info "启动本地开发模式..."

    # 检查 Python 依赖
    if ! python -c "import fastapi" 2>/dev/null; then
        info "安装 Python 依赖..."
        pip install -r "$PROJECT_DIR/backend/requirements.txt" -q
    fi

    # 启动后端
    info "启动后端服务 (端口 $PORT)..."
    cd "$PROJECT_DIR/backend"
    
    # 同时用 Python 简单 HTTP 服务器提供前端
    info "前端页面: http://localhost:$PORT"
    info "API 文档: http://localhost:$PORT/docs"
    echo ""
    
    uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
}

# ============================================================
# Docker 构建
# ============================================================
cmd_docker_build() {
    info "构建 Docker 镜像: $IMAGE_NAME ..."
    cd "$PROJECT_DIR"

    # 检查 .env 文件
    if [ ! -f .env ]; then
        err ".env 文件不存在！请先创建 .env 文件"
        exit 1
    fi

    docker build -t "$IMAGE_NAME" .
    ok "Docker 镜像构建成功: $IMAGE_NAME"
    docker images | grep "$IMAGE_NAME"
}

# ============================================================
# Docker 运行
# ============================================================
cmd_docker_run() {
    info "启动 Docker 容器: $CONTAINER_NAME ..."

    # 停止已有容器
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        warn "容器已在运行，先停止..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
    elif docker ps -aq -f name="$CONTAINER_NAME" | grep -q .; then
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
    fi

    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "$PORT:8000" \
        --env-file "$PROJECT_DIR/.env" \
        -v "$PROJECT_DIR/backend/data:/app/backend/data" \
        --restart unless-stopped \
        "$IMAGE_NAME"

    ok "容器已启动！"
    echo ""
    info "服务地址: http://localhost:$PORT"
    info "API 文档: http://localhost:$PORT/docs"
    info "查看日志: ./deploy.sh docker-logs"
}

# ============================================================
# Docker 停止
# ============================================================
cmd_docker_stop() {
    info "停止容器: $CONTAINER_NAME ..."
    docker stop "$CONTAINER_NAME" 2>/dev/null && ok "容器已停止" || warn "容器未在运行"
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
}

# ============================================================
# Docker 日志
# ============================================================
cmd_docker_logs() {
    docker logs -f "$CONTAINER_NAME" 2>/dev/null || err "容器未运行"
}

# ============================================================
# EdgeOne Pages 部署（前端）
# ============================================================
cmd_edgeone() {
    info "部署前端到 EdgeOne Pages..."
    cd "$PROJECT_DIR"

    # 检查是否安装了 edgeone cli
    if ! command -v edgeone &>/dev/null; then
        warn "未检测到 edgeone CLI，尝试安装..."
        npm install -g @edgeone/cli 2>/dev/null || {
            err "安装 edgeone CLI 失败"
            echo ""
            echo "请手动安装: npm install -g @edgeone/cli"
            echo "或参考文档: https://edgeone.ai/docs/pages/quick-start"
            echo ""
            echo "也可以手动部署："
            echo "  1. 登录 https://edgeone.ai"
            echo "  2. 创建新项目"
            echo "  3. 上传 frontend/ 目录"
            echo "  4. 设置构建输出目录为 frontend"
            exit 1
        }
    fi

    # 部署
    info "正在部署 frontend/ 目录到 EdgeOne Pages..."
    edgeone pages deploy "$PROJECT_DIR/frontend" --project-name "$IMAGE_NAME" 2>&1 || {
        warn "CLI 部署失败，请尝试手动部署："
        echo ""
        echo "方式一：通过 EdgeOne 控制台"
        echo "  1. 访问 https://console.cloud.tencent.com/edgeone/pages"
        echo "  2. 点击「新建项目」→「直接上传」"
        echo "  3. 上传 frontend/ 目录下的所有文件"
        echo "  4. 项目名称填: $IMAGE_NAME"
        echo ""
        echo "方式二：通过 Git 仓库关联"
        echo "  1. 将代码推送到 GitHub"
        echo "  2. 在 EdgeOne Pages 中关联 GitHub 仓库"
        echo "  3. 设置构建输出目录为 frontend"
        echo ""
        echo "方式三：使用 Wrangler (Cloudflare Pages 兼容)"
        echo "  npx wrangler pages deploy frontend/"
    }
}

# ============================================================
# 完整部署
# ============================================================
cmd_full() {
    info "🦊 开始完整部署..."
    echo ""

    # 1. 构建 Docker
    cmd_docker_build
    echo ""

    # 2. 运行 Docker
    cmd_docker_run
    echo ""

    # 3. 部署前端
    cmd_edgeone
    echo ""

    ok "🦊 部署完成！"
}

# ============================================================
# 状态检查
# ============================================================
cmd_status() {
    echo ""
    echo "刘看山推荐 — 服务状态"
    echo "=========================="

    # Docker 状态
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q . 2>/dev/null; then
        ok "Docker 容器: 运行中 ✅"
        docker ps -f name="$CONTAINER_NAME" --format "  端口: {{.Ports}}\n  运行时间: {{.Status}}"
    else
        warn "Docker 容器: 未运行 ❌"
    fi

    # 健康检查
    echo ""
    if curl -s "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
        ok "API 服务: 正常 ✅"
        curl -s "http://localhost:$PORT/api/health" | python -m json.tool 2>/dev/null || true
    else
        warn "API 服务: 不可达 ❌"
    fi

    echo ""
    info "服务地址: http://localhost:$PORT"
    info "API 文档: http://localhost:$PORT/docs"
}

# ============================================================
# 主入口
# ============================================================
case "${1:-}" in
    dev)          cmd_dev ;;
    docker-build) cmd_docker_build ;;
    docker-run)   cmd_docker_run ;;
    docker-stop)  cmd_docker_stop ;;
    docker-logs)  cmd_docker_logs ;;
    edgeone)      cmd_edgeone ;;
    full)         cmd_full ;;
    status)       cmd_status ;;
    *)            usage ;;
esac