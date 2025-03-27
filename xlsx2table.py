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
from modules.column_type_detector import determine_column_type  # 导入字符判断模块

EXCEL_DIR = './upfile'
progress_lock = threading.Lock()
app = Flask(__name__)

# 统一全局变量定义
progress = {'percentage': 0, 'message': '', 'status': '', 'can_stop': True}
import_flag = False  # 重命名为 import_flag 避免与函数名冲突

def excel2mariadb_with_progress(excel_path, username, password, host, database, port):
    global progress, import_flag
    cursor = None
    conn = None
    start_time = time.time()  # 修复：添加 start_time 定义
    try:
        if excel_path.endswith('.xls'):
            engine_type = 'xlrd'
        elif excel_path.endswith('.xlsx'):
            engine_type = 'openpyxl'
        else:
            raise ValueError("不支持的文件类型，请提供 .xls 或 .xlsx 文件。")
        
        progress['percentage'] = 5
        loading_message = "正在读取Excel文件,如果文件较大此过程将会很慢，请耐心等待"
        
        # 创建一个事件来控制加载消息线程
        file_loaded_event = threading.Event()
        
        # 创建一个线程来更新加载消息
        def update_loading_message():
            indicators = ["|", "/", "-", "\\"]
            i = 0
            while not file_loaded_event.is_set():
                with progress_lock:
                    progress['message'] = f"{loading_message} [{indicators[i]}]"
                i = (i + 1) % len(indicators)
                time.sleep(0.2)
        
        loading_thread = threading.Thread(target=update_loading_message, daemon=True)
        loading_thread.start()
        
        # 读取Excel文件
        if excel_path.endswith('.xlsx'):
            df = pd.read_excel(
                excel_path,
                dtype=str,
                keep_default_na=False,
                engine='openpyxl',
                engine_kwargs={
                    'read_only': True,
                    'data_only': True
                }
            )
        else:  # .xls 文件
            df = pd.read_excel(
                excel_path,
                dtype=str,
                keep_default_na=False,
                engine='xlrd'
            )
            
        # 标记文件已加载完成
        file_loaded_event.set()
        
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
            column_type = determine_column_type(df[col])  # 使用导入的函数
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
        
        # 修改：增加批量提交大小，减少网络通信
        batch_size = 10000  # 增加批量大小
        commit_size = 50000  # 每20000条记录提交一次
        
        progress['percentage'] = 30
        progress['message'] = "开始数据导入..."
        
        total_rows = len(df)
        total_batches = (total_rows + batch_size - 1) // batch_size
        column_names = [f"`{col}`" for col in original_columns]
        placeholder = ", ".join(["%s"] * len(original_columns))
        insert_sql = f'INSERT INTO `{table_name}` ({", ".join(column_names)}) VALUES ({placeholder})'

        records_since_commit = 0
        for batch_num in range(total_batches):
            if import_flag:
                progress['message'] = "导入已被用户停止"
                progress['status'] = "已停止"
                progress['can_stop'] = False
                if records_since_commit > 0:
                    conn.commit()
                if cursor:
                    cursor.execute("SET unique_checks=1")
                    cursor.execute("SET foreign_key_checks=1")
                    cursor.execute("SET autocommit=1")
                return "导入已停止"

            start = batch_num * batch_size
            end = min(start + batch_size, total_rows)
            batch = df.iloc[start:end].values
            
            # 数据处理优化：预先处理整个批次的数据
            processed_batch = []
            for row in batch:
                processed_row = []
                for j, col in enumerate(original_columns):
                    cell_value = str(row[j]).strip()
                    if cell_value == '':
                        processed_row.append(None)
                    else:
                        column_type = columns_definition[j]
                        if 'INT' in column_type or 'DECIMAL' in column_type:
                            processed_row.append(cell_value.replace(',', ''))
                        else:
                            processed_row.append(cell_value)
                processed_batch.append(tuple(processed_row))

            cursor.executemany(insert_sql, processed_batch)
            records_since_commit += (end - start)

            # 只在达到commit_size时提交，减少网络通信
            if records_since_commit >= commit_size:
                conn.commit()
                records_since_commit = 0

            progress['percentage'] = int(30 + (batch_num + 1) / total_batches * 70)
            progress['message'] = f"已导入 {end} / {total_rows} 行"
            # 移除 time.sleep

        # 确保最后的数据被提交
        if records_since_commit > 0:
            conn.commit()

        cursor.execute("SET unique_checks=1")
        cursor.execute("SET foreign_key_checks=1")
        cursor.execute("SET autocommit=1")

        progress['percentage'] = 100
        elapsed_time = time.time() - start_time
        progress['message'] = f"导入完成！"
        progress['status'] = f"一共导入 {total_rows} 条数据，用时 {elapsed_time:.2f} 秒。"
        return progress['message']
    except mysql.connector.Error as err:
        progress['percentage'] = 0
        progress['message'] = f"数据库连接失败: {err}"
        progress['status'] = "导入失败"
        progress['can_stop'] = False
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
        return progress['message']
    except Exception as e:
        progress['percentage'] = 0
        progress['message'] = f"发生错误：{str(e)}"
        progress['status'] = "导入失败"
        progress['can_stop'] = False
        if cursor:
            try:
                cursor.execute("SET unique_checks=1")
                cursor.execute("SET foreign_key_checks=1")
                cursor.execute("SET autocommit=1")
            except:
                pass
        return progress['message']
    finally:
        progress['can_stop'] = False
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

# 在文件顶部添加线程锁

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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # 文件名安全处理
            excel_file_name = secure_filename(request.form.get('excel_file', ''))
            if not excel_file_name:
                return "请选择 Excel 文件"

            excel_path = os.path.abspath(os.path.join(EXCEL_DIR, excel_file_name))
            if not os.path.realpath(excel_path).startswith(os.path.realpath(EXCEL_DIR)):
                return "非法文件路径"
            if not os.path.exists(excel_path) or not os.path.isfile(excel_path):
                return f"文件 {excel_file_name} 不存在或不是有效文件"

            # 端口号验证
            try:
                port = int(request.form.get('port', ''))
                if not (0 < port < 65536):
                    return "端口号必须在1-65535之间"
            except ValueError:
                return "端口号必须是有效的数字"

            # 验证数据库参数
            required_fields = ['host', 'username', 'password', 'database', 'port']
            missing_fields = [field for field in required_fields if not request.form.get(field)]
            if missing_fields:
                return f"请填写以下必填字段: {', '.join(missing_fields)}"

            config = {field: request.form.get(field) for field in required_fields}
            save_config(config)

            # 重置导入状态
            # 使用线程锁保护全局变量
            with progress_lock:
                global import_flag, progress
                import_flag = False
                progress = {'percentage': 0, 'message': '', 'status': '', 'can_stop': True}

            thread = threading.Thread(
                target=excel2mariadb_with_progress,
                args=(excel_path, config['username'], config['password'],
                      config['host'], config['database'], str(port)),
                daemon=True  # 设置为守护线程
            )
            thread.start()

            return redirect(url_for('progress_page'))
        except Exception as e:
            app.logger.error(f"导入过程发生错误: {str(e)}", exc_info=True)
            return f"发生错误: {str(e)}"

    try:
        config = load_config()
        file_list = os.listdir(EXCEL_DIR)
        return render_template('index.html', config=config, file_list=file_list)
    except Exception as e:
        app.logger.error(f"加载页面时发生错误: {str(e)}", exc_info=True)
        return "加载页面时发生错误，请检查服务器日志"

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
    try:
        if not os.path.exists(EXCEL_DIR):
            os.makedirs(EXCEL_DIR)
        app.run(debug=False, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"启动服务器失败: {str(e)}")