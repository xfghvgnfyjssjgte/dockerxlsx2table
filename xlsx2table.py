import flask
from flask import Flask, render_template, request, redirect, url_for, jsonify
import pandas as pd
from pathlib import Path
import re
import mysql.connector
import time
import json
import os
import threading
from werkzeug.utils import secure_filename

def determine_column_type(column_values):
    """根据列数据推断数据类型，并处理过长的 VARCHAR 列"""
    original_values = column_values.astype(str).str.strip()  # 保留原始值用于空值检测
    filtered_values = original_values[original_values != ""]
    
    if filtered_values.empty:
        return 'VARCHAR(100)'
    
    # 新增：检查原始数据中是否存在空字符串
    has_empty = (original_values == '').any()
    
    # 日期时间检测（保持不变）
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            pd.to_datetime(column_values, format=fmt, errors='raise')
            return 'DATETIME' if ' ' in fmt else 'DATE'
        except Exception:
            continue
    
    # 检查是否全是数字格式
    numeric_values = filtered_values.str.replace(',', '', regex=True)
    if numeric_values.str.match(r'^-?\d+$').all():
        # 检查数字长度，如果任何值超过10位，使用VARCHAR
        max_digits = numeric_values.str.len().max()
        if max_digits > 10:  # INT最大为10位数字
            return f'VARCHAR({max(max_digits + 5, 30)})'  # 确保足够长度
        # 如果存在空字符串，使用VARCHAR
        if (column_values == '').any():
            return f'VARCHAR({max(max_digits + 5, 30)})'
        return 'INT'
    
    if numeric_values.str.match(r'^-?\d+(\.\d+)?$').all():
        # 同样检查DECIMAL类型可能超范围的情况
        integer_parts = [len(str(val).split('.')[0]) for val in numeric_values if '.' in str(val)]
        if integer_parts and max(integer_parts, default=0) > 12:  # DECIMAL(18,6)最多12位整数部分
            return f'VARCHAR({max(numeric_values.str.len().max() + 5, 30)})'
        # 如果存在空字符串，使用VARCHAR
        if (column_values == '').any():
            return f'VARCHAR({max(numeric_values.str.len().max() + 5, 30)})'
        return 'DECIMAL(18,6)'
    
    # 如果类型混合或无法判断，fallback 到 VARCHAR
    max_length = column_values.str.len().max()
    if max_length <= 50:
        return f'VARCHAR({max_length + 10})'  # 给一点余量
    elif max_length <= 100:
        return 'VARCHAR(100)'
    elif max_length <= 200:
        return 'VARCHAR(200)'
    elif max_length > 255:
        if max_length > 65535:
            return 'LONGTEXT'
        elif max_length > 16383:
            return 'MEDIUMTEXT'
        else:
            return 'TEXT'
    else:
        return 'VARCHAR(255)'

progress = {'percentage': 0, 'message': '', 'status': ''}  # 用于存储进度信息

def excel2mariadb_with_progress(excel_path, username, password, host, database, port):
    global progress
    # 重置进度信息
    progress = {'percentage': 0, 'message': '准备导入...', 'status': ''}
    
    start_time = time.time()
    conn = None
    try:
        if excel_path.endswith('.xls'):
            engine_type = 'xlrd'
        elif excel_path.endswith('.xlsx'):
            engine_type = 'openpyxl'
        else:
            raise ValueError("不支持的文件类型，请提供 .xls 或 .xlsx 文件。")
        
        progress['percentage'] = 5
        progress['message'] = "正在读取Excel文件..."
        
        df = pd.read_excel(excel_path, dtype=str, keep_default_na=False, engine=engine_type)
        original_columns = [str(col).strip() for col in df.columns]
        table_name = Path(excel_path).stem
        table_name = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', table_name)[:30]
        
        progress['percentage'] = 10
        progress['message'] = "正在连接数据库..."
        
        # 根据文件大小动态设置 buffered 参数
        file_size = os.path.getsize(excel_path)
        threshold = 10 * 1024 * 1024  # 10MB
        buffered = file_size < threshold

        conn = mysql.connector.connect(
            user=username, 
            password=password, 
            host=host, 
            database=database, 
            port=int(port), 
            charset='utf8mb4',
            buffered=buffered
        )
        cursor = conn.cursor()
        
        progress['percentage'] = 15
        progress['message'] = "正在分析数据类型..."
        
        cursor.execute(f'DROP TABLE IF EXISTS `{table_name}`')
        columns_definition = []
        
        # 计算预估的行大小
        estimated_row_size = 0
        for col in original_columns:
            column_type = determine_column_type(df[col])
            columns_definition.append(f'`{col}` {column_type}')
            
            # 粗略估计每列占用的字节数
            if 'VARCHAR' in column_type:
                match = re.search(r'VARCHAR\((\d+)\)', column_type)
                if match:
                    varchar_size = int(match.group(1))
                    estimated_row_size += varchar_size * 4 + 3
            elif 'INT' in column_type:
                estimated_row_size += 4
            elif 'DECIMAL' in column_type:
                estimated_row_size += 8
            elif 'DATE' in column_type:
                estimated_row_size += 3
            elif 'DATETIME' in column_type:
                estimated_row_size += 8
                
        progress['percentage'] = 20
        progress['message'] = f"估计的行大小: {estimated_row_size} 字节"
        
        # 如果预估行大小接近或超过限制，进行调整
        if estimated_row_size > 60000:  # 留一些余量
            progress['message'] = f"警告: 表结构可能超出行大小限制(65535)，正在自动调整列类型..."
            
            varchar_columns = []
            for i, col_def in enumerate(columns_definition):
                match = re.search(r'VARCHAR\((\d+)\)', col_def)
                if match:
                    varchar_size = int(match.group(1))
                    varchar_columns.append((i, varchar_size))
            
            varchar_columns.sort(key=lambda x: x[1], reverse=True)
            
            for i, size in varchar_columns:
                if estimated_row_size > 60000:
                    if 'VARCHAR' in columns_definition[i]:
                        estimated_row_size -= (size * 4 + 3)
                        estimated_row_size += 2
                        columns_definition[i] = re.sub(r'VARCHAR\(\d+\)', 'TEXT', columns_definition[i])
                        progress['message'] = f"将列 {original_columns[i]} 从VARCHAR转为TEXT，现在估计行大小: {estimated_row_size} 字节"
                else:
                    break
        
        progress['percentage'] = 25
        progress['message'] = "正在创建表结构..."
        
        ddl = f'CREATE TABLE `{table_name}` ({", ".join(columns_definition)})'
        cursor.execute(ddl)
        
        cursor.execute("SET autocommit=0")
        cursor.execute("SET unique_checks=0")
        cursor.execute("SET foreign_key_checks=0")
        
        progress['percentage'] = 30
        progress['message'] = "开始数据导入..."
        
        total_rows = len(df)
        batch_size = 2000
        total_batches = (total_rows + batch_size - 1) // batch_size
        column_names = [f"`{col}`" for col in original_columns]
        placeholder = ", ".join(["%s"] * len(original_columns))
        insert_sql = f'INSERT INTO `{table_name}` ({", ".join(column_names)}) VALUES ({placeholder})'

        for batch_num in range(total_batches):
            start = batch_num * batch_size
            end = min(start + batch_size, total_rows)
            batch = df.iloc[start:end].values
            # 处理数值类型列（INT 和 DECIMAL）的空字符串，替换为 None
            # 在数据导入循环中增加更严格的空值处理
            for i, row in enumerate(batch):
                for j, col in enumerate(original_columns):
                    cell_value = str(row[j]).strip()
                    # 统一处理所有数值类型的空值
                    if cell_value == '':
                        batch[i][j] = None
                    else:
                        # 额外处理数值类型中的千分位逗号
                        column_type = determine_column_type(df[col])
                        if 'INT' in column_type or 'DECIMAL' in column_type:
                            batch[i][j] = cell_value.replace(',', '')
            batch = [tuple(row) for row in batch]
            cursor.executemany(insert_sql, batch)
            conn.commit()
            progress['percentage'] = int(30 + (batch_num + 1) / total_batches * 70)
            progress['message'] = f"已导入 {end} / {total_rows} 行"
            time.sleep(0.1)

        cursor.execute("SET unique_checks=1")
        cursor.execute("SET foreign_key_checks=1")
        cursor.execute("SET autocommit=1")

        progress['percentage'] = 100
        elapsed_time = time.time() - start_time
        progress['message'] = f"导入完成！"
        progress['status'] = f"一共导入 {total_rows} 条数据，用时 {elapsed_time:.2f} 秒。"
        return progress['message']
    except mysql.connector.Error as err:
        if conn and conn.is_connected():
            cursor = conn.cursor()
            cursor.close()
        progress['percentage'] = 0
        progress['message'] = f"数据库连接失败: {err}"
        progress['status'] = "导入失败"
        return progress['message']
    except Exception as e:
        progress['percentage'] = 0
        progress['message'] = f"发生错误：{str(e)}"
        progress['status'] = "导入失败"
        return progress['message']
    finally:
        if conn and conn.is_connected():
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

EXCEL_DIR = './upfile'
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
            return "请选择 Excel 文件"

        excel_path = os.path.join(EXCEL_DIR, excel_file_name)

        if not os.path.exists(excel_path):
            return f"文件 {excel_file_name} 不存在,请确认目录{EXCEL_DIR}存在并且文件存在"
        config = {
            "host": host,
            "username": username,
            "password": password,
            "database": database,
            "port": port
        }
        save_config(config)

        # 启动后台线程
        threading.Thread(target=excel2mariadb_with_progress, args=(excel_path, username, password, host, database, port)).start()

        return redirect(url_for('progress_page'))

    config = load_config()
    file_list = os.listdir(EXCEL_DIR)
    return render_template('index.html', config=config, file_list=file_list)

@app.route('/progress')
def progress_page():
    return render_template('progress.html')

@app.route('/progress_data')
def progress_data():
    return jsonify(progress)

@app.route('/refresh')
def refresh_file_list():
    """刷新文件列表并返回主页"""
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(EXCEL_DIR):
        os.makedirs(EXCEL_DIR)
    app.run(debug=True, host='0.0.0.0', port=5000)