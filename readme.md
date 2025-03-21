# Excel 到 MariaDB 导入工具

本项目提供一个基于 Web 的工具，用于将 Excel 文件（.xls 或 .xlsx）中的数据导入到 MariaDB 数据库中。它可以自动检测列数据类型，并在数据库中创建相应的表。

## 功能

* 将 Excel 文件（.xls 或 .xlsx）中的数据导入到 MariaDB。
* 自动检测列数据类型（VARCHAR、DECIMAL、DATE、DATETIME）。
* 提供 Web 界面，方便配置和导入过程。
* 显示导入进度和完成状态，包括导入时间和行数。
* 使用 Docker 进行轻松部署和容器化。

## 技术栈

* Flask (Python Web 框架)
* Pandas (数据操作和分析)
* MySQL Connector (MariaDB 数据库连接)
* OpenPyXL 和 xlrd (Excel 文件处理)
* Docker (容器化)

## 安装说明

1.  **克隆仓库：**

    ```bash
    git clone <仓库地址>
    cd <仓库目录>
    ```

2.  **安装 Python 依赖项：**

    ```bash
    pip install -r requirements.txt
    ```

3.  **配置数据库连接：**

    * 在项目根目录中创建一个 `config.json` 文件，结构如下：

        ```json
        {
          "host": "您的数据库主机",
          "username": "您的数据库用户名",
          "password": "您的数据库密码",
          "database": "您的数据库名称",
          "port": "您的数据库端口"
        }
        ```

    * 将占位符替换为您的实际数据库凭据。

4.  **运行应用程序：**

    ```bash
    python xlsx2table.py
    ```

    * 应用程序将在 `http://0.0.0.0:5000` 上可用。

## 使用说明

1.  **打开 Web 界面：**

    * 打开您的 Web 浏览器，导航到 `http://0.0.0.0:5000`。

2.  **输入 Excel 文件路径和数据库凭据：**

    * 在 `upfile` 目录中提供 Excel 文件的路径。
    * 输入数据库连接详细信息。

3.  **开始导入：**

    * 单击“开始导入”按钮。

4.  **监控导入进度：**

    * 您将被重定向到进度页面，该页面显示导入进度和状态。

## 项目结构├── xlsx2table.py
├── templates/
│   ├── index.html
│   └── progress.html
├── upfile/
├── config.json
├── requirements.txt
└── Dockerfile
## Docker

1.  **构建 Docker 镜像：**

    ```bash
    docker build -t excel-to-mariadb .
    ```
2.  **运行 Docker 容器：**
  ```bash
docker run -d \
    --name xx2t \
    -p 5000:5000 \
    -v $(pwd)/upfile:/app/upfile \
    excel-to-mariadb
        ```
       * 应用程序将在 `http://localhost:5000` 上可用。

## 配置

* `config.json`：存储数据库连接详细信息。

## 依赖项

pip install flask pandas mysql-connector-python
## 许可证

本项目使用 MIT 许可证。

## 贡献指南

欢迎贡献！请随时提交拉取请求或打开问题。