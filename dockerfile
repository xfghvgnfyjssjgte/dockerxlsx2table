# 第一阶段：安装依赖
FROM python:3.9-slim as builder

# 设置工作目录
WORKDIR /install

# 复制依赖文件
COPY requirements.txt .

# 安装依赖到指定目录
RUN pip install --no-cache-dir -r requirements.txt -t /install/packages

# 第二阶段：最终镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 从builder阶段复制安装好的依赖
COPY --from=builder /install/packages /usr/local/lib/python3.9/site-packages/

# 复制应用代码
COPY . /app

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "xlsx2table.py"]