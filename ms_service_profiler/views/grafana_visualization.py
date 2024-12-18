# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import re
import sqlite3
import logging
from urllib.parse import urlparse
import datetime
from decimal import Decimal

import pandas as pd

from ms_service_profiler.analyze import check_input_path_valid
from ms_service_profiler.views.datasource import create_datasource
from ms_service_profiler.views.dashboard import create_dashboard

logging.basicConfig(level=logging.INFO)


def check_db_path_valid(path):
    # 校验文件是否存在
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path does not exist: {path}")

    # 校验文件权限，可读写
    file_stat = os.stat(path)
    if not (file_stat.st_mode & 0o664):
        raise argparse.ArgumentTypeError(
            f"Error: The file '{path}' does not have the required read/write permissions (664).")

    # 校验是否为合法sqlite数据库
    with open(path, 'rb') as f:
        header = f.read(16)  # SQLite 文件头长度是16个字节
        sqlite_header = b'SQLite format 3\x00'

        if header != sqlite_header:
            raise argparse.ArgumentTypeError(f"Error: The file '{path}' is not a valid SQLite database file.")
    return path


def check_token_valid(token):
    # 校验是字符串
    if not isinstance(token, str):
        raise argparse.ArgumentTypeError("Error: Grafana token should be a string.")
    # 校验字符串内容
    pattern = r'^[a-zA-Z0-9_]+$'
    if not re.match(pattern, token):
        raise argparse.ArgumentTypeError("Error: Invalid Grafana token format.")
    return token


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
            alloc_value = row['deviceKvCache']
            free_value = kvcache_df[kvcache_df['action'] == 'Free']['deviceKvCache'].values
            if len(free_value) > 0:
                usage_rate = (free_value[0] - alloc_value) / free_value[0]
            else:
                usage_rate = 0  # 如果没有Free的对应值，默认使用率为0
        elif action == 'AppendSlot':
            append_value = row['deviceKvCache']
            free_value = kvcache_df[kvcache_df['action'] == 'Free']['deviceKvCache'].values
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
        df['real_start_time'] = df['start_time'].apply(timestamp_to_datetime)
        df = kvcache_usage_rate_calculator(df)
    return df


def save_csv_to_sqlite(input_path):
    db_path = os.path.join(input_path, '.' + 'profiler.db')  # 隐藏文件
    csv_whitelist = ['batch.csv', 'kvcache.csv', 'request.csv', "request_status.csv"]
    conn = sqlite3.connect(db_path)

    for filename in os.listdir(input_path):
        if filename.endswith('.csv') and filename in csv_whitelist:
            csv_path = os.path.join(input_path, filename)
            df = pd.read_csv(csv_path, encoding='utf-8')
            df = add_column_to_kvcache(filename, df)
            table_name = os.path.splitext(filename)[0]
            df.to_sql(table_name, conn, if_exists='replace', index=False)

    conn.commit()
    conn.close()
    return check_db_path_valid(db_path)


def main():
    parser = argparse.ArgumentParser(description="Process database path.")
    parser.add_argument('--input_path', type=check_input_path_valid, help="Path to the CSV expoter folder")
    parser.add_argument('--token', type=check_token_valid, help="Grafana token")
    parser.add_argument('--url', type=check_url_valid, default="http://localhost:3000", help="Grafana URL")
    args = parser.parse_args()
    db_path = save_csv_to_sqlite(args.input_path)
    datasource_uid = create_datasource(args.url, args.token, db_path)
    grafana_url = create_dashboard(args.url, args.token, datasource_uid)
    logging.info(f"Please log in {grafana_url} to view the dashboard 'Profiler Visualization'")


if __name__ == "__main__":
    main()
