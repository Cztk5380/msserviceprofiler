import argparse
import os
import re
import logging
from urllib.parse import urlparse

from datasource import create_datasource
from dashboard import create_dashboard

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


def main():
    parser = argparse.ArgumentParser(description="Process database path.")
    parser.add_argument('--db_path', type=check_db_path_valid, help="Path to the SQLite database")
    parser.add_argument('--token', type=check_token_valid, help="Grafana token")
    parser.add_argument('--url', type=check_url_valid, default="http://localhost:3000", help="Grafana URL")
    args = parser.parse_args()
    datasource_uid = create_datasource(args.url, args.token, args.db_path)
    grafana_url = create_dashboard(args.url, args.token, datasource_uid)
    logging.info(f"Please log in  {grafana_url} to view the dashboard 'Profiler Visualization'")


if __name__ == "__main__":
    main()