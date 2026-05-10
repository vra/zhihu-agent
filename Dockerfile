# 刘看山推荐 - 后端服务 Docker 镜像
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY liukanshan/ ./liukanshan/
COPY .env .

# 创建数据目录
RUN mkdir -p /app/backend/data

# 设置工作目录为 backend
WORKDIR /app/backend

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]