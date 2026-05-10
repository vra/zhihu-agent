#!/bin/bash
# ============================================================
# 刘看山推荐 — 一键部署脚本
# 支持: 本地开发 / Docker 部署 / EdgeOne Pages 前端部署
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
BACKEND_URL="${BACKEND_URL:-}"

# ============================================================
# 用法
# ============================================================
usage() {
    echo ""
    echo "刘看山推荐 — 部署脚本"
    echo ""
    echo "用法: ./deploy.sh <command> [options]"
    echo ""
    echo "命令:"
    echo "  dev              本地开发模式（启动后端服务）"
    echo "  docker-build     构建 Docker 镜像"
    echo "  docker-run       运行 Docker 容器"
    echo "  docker-stop      停止 Docker 容器"
    echo "  docker-logs      查看 Docker 日志"
    echo "  edgeone          部署前端到 EdgeOne Pages"
    echo "  edgeone-setup    配置 EdgeOne Pages 项目"
    echo "  full             完整部署（Docker 后端 + EdgeOne 前端）"
    echo "  status           查看服务状态"
    echo ""
    echo "环境变量:"
    echo "  PORT             后端服务端口 (默认: 8000)"
    echo "  BACKEND_URL      后端 API 地址 (EdgeOne 部署时需要)"
    echo ""
    echo "示例:"
    echo "  ./deploy.sh dev                              # 本地开发"
    echo "  ./deploy.sh docker-build && ./deploy.sh docker-run  # Docker 部署"
    echo "  BACKEND_URL=https://api.example.com ./deploy.sh edgeone  # EdgeOne 部署"
    echo ""
}

# ============================================================
# 本地开发
# ============================================================
cmd_dev() {
    info "启动本地开发模式..."

    # 检查 .env 文件
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        err ".env 文件不存在！请先创建 .env 文件（参考 .env.example）"
        exit 1
    fi

    # 检查 Python 依赖
    if ! python3 -c "import fastapi" 2>/dev/null; then
        info "安装 Python 依赖..."
        pip3 install -r "$PROJECT_DIR/backend/requirements.txt" -q
    fi

    # 清除代理环境变量（避免 SOCKS 代理问题）
    unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

    info "启动后端服务 (端口 $PORT)..."
    info "前端页面: http://localhost:$PORT"
    info "API 文档: http://localhost:$PORT/docs"
    echo ""

    cd "$PROJECT_DIR/backend"
    python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
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
# EdgeOne Pages 配置
# ============================================================
cmd_edgeone_setup() {
    info "配置 EdgeOne Pages 项目..."

    # 检查后端 URL
    if [ -z "$BACKEND_URL" ]; then
        echo ""
        warn "未设置 BACKEND_URL 环境变量"
        echo ""
        echo "EdgeOne Pages 部署前端静态文件，需要指定后端 API 地址。"
        echo ""
        echo "请先部署后端服务（Docker 或云服务器），获取后端地址后运行："
        echo ""
        echo "  BACKEND_URL=https://your-backend.com ./deploy.sh edgeone-setup"
        echo ""
        echo "如果只是本地测试，可以使用："
        echo "  BACKEND_URL=http://localhost:8000 ./deploy.sh edgeone-setup"
        echo ""
        read -p "请输入后端 API 地址 (直接回车使用 http://localhost:8000): " input_url
        BACKEND_URL="${input_url:-http://localhost:8000}"
    fi

    info "后端 API 地址: $BACKEND_URL"

    # 创建 EdgeOne 部署专用的前端文件
    DEPLOY_DIR="$PROJECT_DIR/frontend-deploy"
    rm -rf "$DEPLOY_DIR"
    mkdir -p "$DEPLOY_DIR"

    # 复制前端文件并替换 API_BASE
    cp "$PROJECT_DIR/frontend/index.html" "$DEPLOY_DIR/index.html"

    # 替换 API_BASE 为实际后端地址
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|const API_BASE = window.location.origin;|const API_BASE = '${BACKEND_URL}';|g" "$DEPLOY_DIR/index.html"
    else
        sed -i "s|const API_BASE = window.location.origin;|const API_BASE = '${BACKEND_URL}';|g" "$DEPLOY_DIR/index.html"
    fi

    # 更新 edgeone.json
    cat > "$PROJECT_DIR/edgeone.json" << EOJSON
{
  "name": "liukanshan-recommend",
  "build": {
    "output": "frontend-deploy"
  },
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/index.html"
    }
  ]
}
EOJSON

    ok "EdgeOne 部署文件已准备好"
    info "部署目录: $DEPLOY_DIR"
    info "API 地址: $BACKEND_URL"
    echo ""
    echo "下一步: 运行 ./deploy.sh edgeone 进行部署"
}

# ============================================================
# EdgeOne Pages 部署（前端）
# ============================================================
cmd_edgeone() {
    info "部署前端到 EdgeOne Pages..."
    cd "$PROJECT_DIR"

    # 确定部署目录
    DEPLOY_DIR="$PROJECT_DIR/frontend-deploy"
    if [ ! -d "$DEPLOY_DIR" ]; then
        warn "未找到部署目录，先运行配置..."
        cmd_edgeone_setup
    fi

    # 检查是否安装了 edgeone CLI
    if command -v edgeone &>/dev/null; then
        info "使用 EdgeOne CLI 部署..."
        edgeone pages deploy "$DEPLOY_DIR" --project-name "$IMAGE_NAME"
        ok "EdgeOne Pages 部署成功！"
        return
    fi

    # 检查是否安装了 npx
    if command -v npx &>/dev/null; then
        info "使用 npx 运行 EdgeOne CLI..."
        npx @edgeone/cli pages deploy "$DEPLOY_DIR" --project-name "$IMAGE_NAME" 2>&1 && {
            ok "EdgeOne Pages 部署成功！"
            return
        }
    fi

    # 手动部署指引
    warn "未检测到 EdgeOne CLI"
    echo ""
    echo "=========================================="
    echo "  EdgeOne Pages 手动部署指南"
    echo "=========================================="
    echo ""
    echo "方式一：安装 CLI 后部署"
    echo "  npm install -g @edgeone/cli"
    echo "  edgeone pages deploy $DEPLOY_DIR --project-name $IMAGE_NAME"
    echo ""
    echo "方式二：通过 EdgeOne 控制台上传"
    echo "  1. 访问 https://console.cloud.tencent.com/edgeone/pages"
    echo "  2. 点击「新建项目」->「直接上传」"
    echo "  3. 上传 frontend-deploy/ 目录下的文件"
    echo "  4. 项目名称填: $IMAGE_NAME"
    echo ""
    echo "方式三：通过 GitHub 仓库关联"
    echo "  1. 将代码推送到 GitHub"
    echo "  2. 在 EdgeOne Pages 中关联 GitHub 仓库"
    echo "  3. 设置构建输出目录为 frontend-deploy"
    echo "  4. 或直接设置为 frontend（如果前后端同域部署）"
    echo ""
    echo "=========================================="
}

# ============================================================
# 完整部署
# ============================================================
cmd_full() {
    info "开始完整部署..."
    echo ""

    # 1. 构建 Docker
    cmd_docker_build
    echo ""

    # 2. 运行 Docker
    cmd_docker_run
    echo ""

    # 3. 配置并部署前端
    if [ -z "$BACKEND_URL" ]; then
        BACKEND_URL="http://localhost:$PORT"
    fi
    cmd_edgeone_setup
    cmd_edgeone
    echo ""

    ok "部署完成！"
    echo ""
    info "后端服务: http://localhost:$PORT"
    info "API 文档: http://localhost:$PORT/docs"
}

# ============================================================
# 状态检查
# ============================================================
cmd_status() {
    echo ""
    echo "刘看山推荐 — 服务状态"
    echo "=========================="

    # Docker 状态
    if docker ps -q -f name="$CONTAINER_NAME" 2>/dev/null | grep -q .; then
        ok "Docker 容器: 运行中"
        docker ps -f name="$CONTAINER_NAME" --format "  端口: {{.Ports}}\n  运行时间: {{.Status}}"
    else
        warn "Docker 容器: 未运行"
    fi

    # 本地进程检查
    echo ""
    if lsof -ti :$PORT >/dev/null 2>&1; then
        ok "端口 $PORT: 已占用（服务运行中）"
    else
        warn "端口 $PORT: 未占用"
    fi

    # 健康检查
    echo ""
    if curl -s "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
        ok "API 服务: 正常"
        curl -s "http://localhost:$PORT/api/health" | python3 -m json.tool 2>/dev/null || true
    else
        warn "API 服务: 不可达"
    fi

    echo ""
    info "服务地址: http://localhost:$PORT"
    info "API 文档: http://localhost:$PORT/docs"
}

# ============================================================
# 主入口
# ============================================================
case "${1:-}" in
    dev)            cmd_dev ;;
    docker-build)   cmd_docker_build ;;
    docker-run)     cmd_docker_run ;;
    docker-stop)    cmd_docker_stop ;;
    docker-logs)    cmd_docker_logs ;;
    edgeone)        cmd_edgeone ;;
    edgeone-setup)  cmd_edgeone_setup ;;
    full)           cmd_full ;;
    status)         cmd_status ;;
    *)              usage ;;
esac