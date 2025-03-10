# 使用官方 Python 3.12 镜像作为基础镜像
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12-slim

# 设置工作目录
WORKDIR /app

# 配置中国镜像源
RUN rm -rf /etc/apt/sources.list.d/* && \
    echo "deb https://mirrors.ustc.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.ustc.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.ustc.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.ustc.edu.cn/debian-security/ bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装系统依赖和 git
RUN apt-get update && apt-get install -y \
    git \
    && rm -r /var/lib/apt/lists/*

# 克隆 OpenManus 仓库（包含 requirements.txt 和 config/config.example.toml）
RUN git clone https://github.com/mannaandpoem/OpenManus.git .

# 安装 Python 依赖，通过国内镜像源
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 创建 config 目录并复制示例配置文件（如果需要覆盖，可通过 volume 挂载）
RUN mkdir -p config && cp config.example.toml config/config.toml

# 启动命令
CMD ["python", "main.py"]