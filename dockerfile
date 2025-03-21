# 使用Python 3.9作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件到工作目录
COPY . /app

# 安装依赖
RUN pip install --no-cache-dir flask pandas mysql-connector-python openpyxl xlrd

# 暴露端口
EXPOSE 5000

# 运行Flask应用
CMD ["python", "xlsx2table.py"]