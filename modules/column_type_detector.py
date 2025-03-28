import pandas as pd
import re

def determine_column_type(column_values):
    """根据列数据推断数据类型，并处理过长的 VARCHAR 列"""
    original_values = column_values.astype(str).str.strip()
    filtered_values = original_values[original_values != ""]
    
    if filtered_values.empty:
        return 'VARCHAR(100)'
    
    has_empty = (original_values == '').any()
    
    # 扩展日期时间格式支持
    DATE_FORMATS = (
        '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',  # 标准日期格式
        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',  # 标准日期时间
        '%Y年%m月%d日', '%Y年%m月%d日 %H时%M分%S秒',  # 中文格式
        '%d/%m/%Y', '%m/%d/%Y',  # 其他常见格式
        '%Y%m%d'  # 紧凑格式
    )
    
    for fmt in DATE_FORMATS:
        try:
            pd.to_datetime(filtered_values, format=fmt, errors='raise')
            return 'DATETIME' if any(x in fmt for x in ['%H', '%M', '%S', '时', '分', '秒']) else 'DATE'
        except Exception:
            continue
    
    # 增强数字格式识别
    # 预处理：移除千位分隔符和货币符号
    numeric_values = filtered_values.str.replace(r'[,¥$€£]', '', regex=True)
    
    # 检查科学计数法
    if numeric_values.str.match(r'^-?\d+\.?\d*[eE][+-]?\d+$').all():
        return 'DOUBLE'
    
    # 检查整数（包括带分隔符的）
    if numeric_values.str.match(r'^-?\d+$').all():
        max_digits = numeric_values.str.len().max()
        if max_digits > 10 or has_empty:
            return f'VARCHAR({max(max_digits + 5, 30)})'
        return 'INT'
    
    # 检查小数（包括货币）
    if numeric_values.str.match(r'^-?\d*\.?\d+$').all():
        max_decimal_length = 0
        max_integer_length = 0
        
        for val in numeric_values:
            parts = str(val).split('.')
            max_integer_length = max(max_integer_length, len(parts[0].replace('-', '')))
            if len(parts) > 1:
                max_decimal_length = max(max_decimal_length, len(parts[1]))
        
        if has_empty:
            total_length = max_integer_length + (max_decimal_length > 0 and max_decimal_length + 1 or 0)
            return f'VARCHAR({max(total_length + 5, 30)})'
        
        if max_decimal_length > 6 or max_integer_length > 12:
            return 'DOUBLE'
        else:
            precision = min(max_integer_length + max_decimal_length, 18)
            scale = min(max_decimal_length, 6)
            return f'DECIMAL({precision},{scale})'
    
    # VARCHAR和TEXT的处理逻辑保持不变
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