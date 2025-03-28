# Excel 自动导入 MariaDB 工具

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.0%2B-lightgrey)
![Docker](https://img.shields.io/badge/docker-支持-success)

基于Web的Excel数据导入工具，支持自动检测数据结构并创建MariaDB表。

## 功能特性

- 📊 Excel (.xls/.xlsx) .csv 到 MariaDB 的数据迁移
- 🔍 自动列类型检测（VARCHAR, DECIMAL, DATE, DATETIME）
- 🌐 网页可视化操作界面
- 📈 实时导入进度监控
- 🐳 Docker 容器化支持

## 技术栈

* Flask (Python Web框架)
* Pandas (数据处理与分析)
* MySQL Connector (MariaDB数据库连接)
* OpenPyXL 和 xlrd (Excel文件处理)
* Docker (容器化部署)

## 项目结构

```
.
├── Dockerfile                 # 容器配置文件
├── modules/                   # 功能模块
│   ├── database.py            # 数据库操作模块
│   └── excel_processor.py     # Excel处理模块
├── README.md                  # 说明文档
├── requirements.txt           # 依赖清单
├── templates/                 # 网页模板
│   ├── index.html             # 主界面
│   └── progress.html          # 进度页面
├── upfile/                    # Excel上传目录
└── xlsx2table.py              # 主程序
```

## 安装指南

### 常规安装

1. 克隆仓库：
   ```bash
   git clone https://github.com/xfghvgnfyjssjgte/dockerxlsx2table.git
   cd excel-to-mariadb
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置数据库 (`config.json`)：
   ```json
   {
     "host": "数据库地址",
     "username": "用户名",
     "password": "密码",
     "database": "目标数据库",
     "port": 3306
   }
   ```

### Docker安装

1. 构建镜像：
   ```bash
   docker build -t excel-importer .
   ```

2. 运行容器：
   ```bash
   docker run -d \
     -p 5000:5000 \
     -v ./upfile:/app/upfile \
     -v ./config.json:/app/config.json \
     --name excel-importer \
     excel-importer
   ```

## 使用说明

1. 将Excel文件放入 `./upfile` 目录
2. 访问 `http://localhost:5000`
3. 选择文件并配置导入参数
4. 在 `/progress` 页面查看实时进度

## API接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 文件上传界面 |
| `/upload` | POST | 处理Excel文件 |
| `/progress` | GET | 导入状态查询 |

## 开发模式

```bash
# 开发模式运行
FLASK_ENV=development python xlsx2table.py

# 运行测试
python -m unittest discover modules/tests
```

## 依赖清单

`requirements.txt` 内容：
```
flask==2.0.3
pandas==1.3.4
mysql-connector-python==8.0.26
openpyxl==3.0.9
xlrd==2.0.1
```

## 开源协议

MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 贡献指南

1. Fork 本仓库
2. 新建功能分支 (`git checkout -b feature/新功能`)
3. 提交代码 (`git commit -am '添加新功能'`)
4. 推送分支 (`git push origin feature/新功能`)
5. 提交Pull Request

---

> ​**重要提示**：生产环境部署时请注意：
> - 妥善保管数据库凭据
> - 为 `upfile` 目录设置适当权限
> - 在 `xlsx2table.py` 中配置日志记录