# 使用官方 Python 3.12 镜像作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖和 git
RUN apt-get update && apt-get install -y \
    git \
    && rm -r /var/lib/apt/lists/*

# 克隆 OpenManus 仓库（包含 requirements.txt 和 config/config.example.toml）
RUN git clone https://github.com/mannaandpoem/OpenManus.git .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建 config 目录并复制示例配置文件（如果需要覆盖，可通过 volume 挂载）
RUN mkdir -p config && cp config.example.toml config/config.toml

# 启动命令
CMD ["python", "main.py"]