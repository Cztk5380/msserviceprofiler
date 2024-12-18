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

import pandas as pd
from urllib.parse import urlparse

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


def save_csv_to_sqlite(input_path):
    db_path = os.path.join(input_path, '.' + 'profiler.db')  # 隐藏文件
    csv_whitelist = ['batch.csv', 'kvcache.csv', 'request.csv', "request_status.csv"]
    conn = sqlite3.connect(db_path)

    for filename in os.listdir(input_path):
        if filename.endswith('.csv') and filename in csv_whitelist:
            csv_path = os.path.join(input_path, filename)
            df = pd.read_csv(csv_path, encoding='utf-8')
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
