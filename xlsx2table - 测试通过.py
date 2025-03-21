import flask
from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
from pathlib import Path
import re
import mysql.connector
import time
import json
import os

def determine_column_type(column_values):
    """根据列数据推断数据类型"""
    column_values = column_values.astype(str).str.strip()
    column_values = column_values[column_values != ""]
    if column_values.empty:
        return 'VARCHAR(255)'
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            pd.to_datetime(column_values, format=fmt, errors='raise')
            return 'DATETIME' if ' ' in fmt else 'DATE'
        except Exception:
            continue
    numeric_values = column_values.str.replace(',', '', regex=True)
    if numeric_values.str.match(r'^-?\d+$').all():
        return 'VARCHAR(255)'
    if numeric_values.str.match(r'^-?\d+(\.\d+)?$').all():
        return 'DECIMAL(18,6)'
    return 'VARCHAR(255)'

def excel2mariadb_with_progress(excel_path, username, password, host, database, port):
    start_time = time.time()
    conn = None 
    try:
        if excel_path.endswith('.xls'):
            engine_type = 'xlrd'
        elif excel_path.endswith('.xlsx'):
            engine_type = 'openpyxl'
        else:
            raise ValueError("不支持的文件类型，请提供 .xls 或 .xlsx 文件。")
        df = pd.read_excel(excel_path, dtype=str, keep_default_na=False, engine=engine_type)
        original_columns = [str(col).strip() for col in df.columns]
        table_name = Path(excel_path).stem
        table_name = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', table_name)[:30]
        conn = mysql.connector.connect(user=username, password=password, host=host, database=database, port=int(port))
        cursor = conn.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS `{table_name}`')
        columns_definition = []
        for col in original_columns:
            column_type = determine_column_type(df[col])
            columns_definition.append(f'`{col}` {column_type}')
        ddl = f'CREATE TABLE `{table_name}` ({", ".join(columns_definition)})'
        cursor.execute(ddl)
        cursor.execute("SET autocommit=0")
        cursor.execute("SET unique_checks=0")
        cursor.execute("SET foreign_key_checks=0")
        total_rows = len(df)
        batch_size = 5000
        total_batches = (total_rows + batch_size - 1) // batch_size
        column_names = [f"`{col}`" for col in original_columns]
        placeholder = ", ".join(["%s"] * len(original_columns))
        insert_sql = f'INSERT INTO `{table_name}` ({", ".join(column_names)}) VALUES ({placeholder})'

        for batch_num in range(total_batches):
            start = batch_num * batch_size
            end = min(start + batch_size, total_rows)
            batch = [tuple(None if v == '' else v for v in row) for row in df.iloc[start:end].values]
            cursor.executemany(insert_sql, batch)
            conn.commit()

        cursor.execute("SET unique_checks=1")
        cursor.execute("SET foreign_key_checks=1")
        cursor.execute("SET autocommit=1")

        return f"导入完成！\n导入行数：{total_rows}\n耗时：{time.time() - start_time:.2f}秒"
    except mysql.connector.Error as err:
        return f"数据库连接失败: {err}"
    except Exception as e:
        return f"发生错误：{str(e)}"
    finally:
        if conn:  
            conn.close()

def load_config():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_config(config):
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        return f"保存配置文件失败: {str(e)}"

EXCEL_DIR = './upfile' #修改了EXCEL_DIR
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        excel_file_name = request.form.get('excel_file')
        host = request.form.get('host')
        username = request.form.get('username')
        password = request.form.get('password')
        database = request.form.get('database')
        port = request.form.get('port')

        if not excel_file_name:
            return "请输入 Excel 文件名"

        # 拼接完整的文件路径
        excel_file = os.path.join(EXCEL_DIR, excel_file_name)

        if not os.path.exists(excel_file):
            return f"文件 {excel_file_name} 不存在,请确认目录{EXCEL_DIR}存在并且文件存在"
        config = {
            "host": host,
            "username": username,
            "password": password,
            "database": database,
            "port": port
        }
        save_config(config)

        try:
            result = excel2mariadb_with_progress(excel_path=excel_file, username=username, password=password, host=host, database=database, port=port)
            return result
        except Exception as e:
            return f"发生错误: {str(e)}"

    config = load_config()
    return render_template('index.html', config=config)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)