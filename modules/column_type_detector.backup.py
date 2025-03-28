import pandas as pd
import re

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
        # 分析数值特征
        max_decimal_length = 0
        for val in numeric_values:
            if '.' in str(val):
                decimal_part = str(val).split('.')[1]
                max_decimal_length = max(max_decimal_length, len(decimal_part))
        
        # 如果存在空字符串，使用VARCHAR
        if (column_values == '').any():
            return f'VARCHAR({max(numeric_values.str.len().max() + 5, 30)})'
        
        # 如果小数位数大于6位，使用DOUBLE
        # 否则使用DECIMAL以保证精确性
        if max_decimal_length > 6:
            return 'DOUBLE'
        else:
            return f'DECIMAL({min(18, max_decimal_length + 12)},{min(max_decimal_length, 6)})'
    # 删除这里的多余return语句
    
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