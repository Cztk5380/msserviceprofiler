# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import argparse
import os
import re
import sqlite3
from urllib.parse import urlparse
import datetime
from decimal import Decimal

import pandas as pd

from ms_service_profiler.analyze import check_input_path_valid
from ms_service_profiler.views.datasource import create_datasource
from ms_service_profiler.views.dashboard import create_dashboard
from ms_service_profiler.utils.log import set_log_level, logger


def check_db_path_valid(path):
    # 校验文件是否存在
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path does not exist: {path}")

    # 校验文件权限，可读写
    file_stat = os.stat(path)
    if not (file_stat.st_mode & 0o664):
        raise argparse.ArgumentTypeError(
            f"The file '{path}' does not have the required read/write permissions (664).")

    # 校验是否为合法sqlite数据库
    with open(path, 'rb') as f:
        header = f.read(16)  # SQLite 文件头长度是16个字节
        sqlite_header = b'SQLite format 3\x00'

        if header != sqlite_header:
            raise argparse.ArgumentTypeError(f"The file '{path}' is not a valid SQLite database file.")
    return path


def check_token_valid(token):
    # 校验是字符串
    if not isinstance(token, str):
        raise argparse.ArgumentTypeError("Grafana token should be a string.")
    # 校验字符串内容
    pattern = r'^[a-zA-Z0-9_]+$'
    if not re.match(pattern, token):
        raise argparse.ArgumentTypeError("Invalid Grafana token format.")
    return token


def check_host_valid(host):
    # 校验是否为字符串
    if not isinstance(host, str):
        raise argparse.ArgumentTypeError("Grafana host should be a string.")
    # 校验字符串内容
    pattern = r'^[a-zA-Z0-9.-]+$'
    if not re.match(pattern, host):
        raise argparse.ArgumentTypeError("Invalid Grafana host format.")
    return host


def check_port_valid(port):
    if int(port) < 1 or int(port) > 65535:
        raise argparse.ArgumentTypeError("Grafana port should be in the range of 1-65535.")
    return port


def check_url_valid(url):
    parsed_url = urlparse(url)

    # 检查URL是否包含有效的scheme和netloc
    if not parsed_url.scheme or not parsed_url.netloc:
        raise argparse.ArgumentTypeError(f"Invalid URL: {url}, please check.")

    return url


def timestamp_to_datetime(timestamp):
    """
    将传入的科学计数法的时间戳转换为真实时间，并在后续处理中存入kvcache.db文件中
    :param timestamp: 科学计数法时间戳
    :return: 真实时间
    """
    # 传入数据为科学计数法的时间戳数据
    timestamp_sci = timestamp

    # 将科学计数法的时间戳转换为Decimal类型
    timestamp_normal = Decimal(timestamp_sci)

    # 将Decimal类型转换为浮点数类型，以便后续能被fromtimestamp函数正确使用
    timestamp_seconds = float(timestamp_normal / 1000000)

    # 将秒数转换为datetime对象
    date_time = datetime.datetime.fromtimestamp(timestamp_seconds)

    return date_time.strftime("%Y-%m-%d %H:%M:%S:%f")


def kvcache_usage_rate_calculator(kvcache_df):
    """
    根据不同的action计算kvcache_usage_rate列的值，并添加到传入的DataFrame中
    """
    # 创建一个空的列表，用于存储计算得到的使用率值
    usage_rate_list = []
    for _, row in kvcache_df.iterrows():
        action = row['action']
        if action == 'KVCacheAlloc':
            alloc_value = row['device_kvcache_left']
            free_value = kvcache_df[kvcache_df['action'] == 'Free']['device_kvcache_left'].values
            if len(free_value) > 0:
                usage_rate = (free_value[0] - alloc_value) / free_value[0]
            else:
                usage_rate = 0  # 如果没有Free的对应值，默认使用率为0
        elif action == 'AppendSlot':
            append_value = row['device_kvcache_left']
            free_value = kvcache_df[kvcache_df['action'] == 'Free']['device_kvcache_left'].values
            if len(free_value) > 0:
                usage_rate = (free_value[0] - append_value) / free_value[0]
            else:
                usage_rate = 0  # 如果没有Free的对应值，默认使用率为0
        elif action == 'Free':
            usage_rate = 0
        else:
            usage_rate = None  # 对于其他action情况，使用率设为None，可根据需求调整
        usage_rate_list.append(usage_rate)

    kvcache_df['kvcache_usage_rate'] = usage_rate_list
    return kvcache_df


def add_column_to_kvcache(file_name, df):
    """在kvcache表中新增real_time和使用率"""
    file_name = file_name
    if file_name == 'kvcache.csv':
        df['real_start_time'] = df['start_time(microsecond)'].apply(timestamp_to_datetime)
        df = kvcache_usage_rate_calculator(df)
    return df


def save_csv_to_sqlite(input_path):
    db_path = os.path.join(input_path, '.profiler.db')
    csv_whitelist = ['batch.csv', 'kvcache.csv', 'request.csv', ".request_status.csv"]
    conn = sqlite3.connect(db_path)

    for filename in os.listdir(input_path):
        if filename.endswith('.csv') and filename in csv_whitelist:
            csv_path = os.path.join(input_path, filename)
            df = pd.read_csv(csv_path, encoding='utf-8')
            df = add_column_to_kvcache(filename, df)
            table_name = os.path.splitext(filename)[0]
            if table_name.startswith('.'):
                table_name = table_name[1:]
            df.to_sql(table_name, conn, if_exists='replace', index=False)

    conn.commit()
    conn.close()
    return check_db_path_valid(db_path)


def main():
    parser = argparse.ArgumentParser(description="Process database path.")
    parser.add_argument('--input_path', type=check_input_path_valid, help="Path to the CSV expoter folder")
    parser.add_argument('--token', type=check_token_valid, help="Grafana token")
    parser.add_argument('--host', type=check_host_valid, default="localhost", help="Grafana host")
    parser.add_argument('--port', type=check_port_valid, default=3000, help="Grafana port")
    parser.add_argument('--log_level', type=str, default='info', \
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'], help='Log level to print')
    args = parser.parse_args()
    set_log_level(args.log_level)
    db_path = save_csv_to_sqlite(args.input_path)
    url = check_url_valid(f"http://{args.host}:{args.port}")
    datasource_uid = create_datasource(url, args.token, db_path)
    grafana_url = create_dashboard(url, args.token, datasource_uid)
    logger.info(f"Please log in {grafana_url} to view the dashboard 'Profiler Visualization'")


if __name__ == "__main__":
    main()
