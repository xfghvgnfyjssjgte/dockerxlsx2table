# Excel to MariaDB Import Tool

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.0%2B-lightgrey)
![Docker](https://img.shields.io/badge/docker-supported-success)

A web-based tool for importing Excel data (.xls/.xlsx) into MariaDB with automatic schema detection.

## Features

- 📊 Excel and csv to MariaDB data migration
- 🔍 Automatic column type detection (VARCHAR, DECIMAL, DATE, DATETIME)
- 🌐 Web interface for easy configuration
- 📈 Real-time progress tracking
- 🐳 Docker container support

## Tech Stack

* Flask (Python web framework)
* Pandas (data manipulation and analysis)
* MySQL Connector (MariaDB database connection)
* OpenPyXL and xlrd (Excel file processing)
* Docker (containerization)

## Project Structure

```
.
├── Dockerfile
├── modules/
│   ├── database.py
│   └── excel_processor.py
├── README.md
├── requirements.txt
├── templates/
│   ├── index.html
│   └── progress.html
├── upfile/
└── xlsx2table.py
```

## Installation

### Manual Setup

1. Clone repository:
   ```bash
   git clone https://github.com/xfghvgnfyjssjgte/dockerxlsx2table.git
   cd excel-to-mariadb
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure database in `config.json`:
   ```json
   {
     "host": "localhost",
     "username": "db_user",
     "password": "db_password",
     "database": "target_db",
     "port": 3306,
     "auto_create_tables": true,
     "default_string_length": 255,
     "date_format": "%Y-%m-%d",
     "batch_size": 1000
   }
   ```

### Docker Setup

1. Build the image:
   ```bash
   docker build -t excel-importer .
   ```

2. Run container:
   ```bash
   docker run -d \
     -p 5000:5000 \
     -v ./upfile:/app/upfile \
     -v ./config.json:/app/config.json \
     --name excel-importer \
     excel-importer
   ```

## Usage

1. Place Excel files in `./upfile` directory
2. Access web interface at `http://localhost:5000`
3. Select file and configure import settings
4. Monitor progress on `/progress` page

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Upload interface |
| `/upload` | POST | Process Excel file |
| `/progress` | GET | Import status |

## Development

```bash
# Run in development mode
FLASK_ENV=development python xlsx2table.py

# Run tests
python -m unittest discover modules/tests
```

## Dependencies

Listed in `requirements.txt`:
```
flask==2.0.3
pandas==1.3.4
mysql-connector-python==8.0.26
openpyxl==3.0.9
xlrd==2.0.1
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request

---

> ​**Note**: For production deployment, ensure to:
> - Secure your database credentials
> - Set appropriate file permissions for the `upfile` directory
> - Configure proper logging in `xlsx2table.py`