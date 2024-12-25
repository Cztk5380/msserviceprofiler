# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from unittest.mock import patch, MagicMock
import os
import argparse
import pytest

import ms_service_profiler.views.grafana_visualization as visual


@patch("os.path.exists")
def test_check_db_path_valid_when_path_not_exist(mock_exists):
    path = '/fake/path/sqlite.db'
    mock_exists.return_value = False  # 模拟文件不存在

    with pytest.raises(argparse.ArgumentTypeError) as exc_info:
        visual.check_db_path_valid(path)

    assert str(exc_info.value) == f"Path does not exist: {path}"


@patch("os.path.exists")
@patch("os.stat")
@patch("builtins.open", new_callable=MagicMock)
def test_check_db_path_valid_when_sqlite_invalid(mock_open, mock_stat, mock_exists):
    path = '/fake/path/sqlite.db'
    mock_exists.return_value = True  # 文件存在
    mock_stat.return_value.st_mode = 0o664  # 权限符合要求
    mock_open.return_value.read.return_value = b"NotSQLite"  # 模拟文件头不是 SQLite 的标识

    with pytest.raises(argparse.ArgumentTypeError) as exc_info:
        visual.check_db_path_valid(path)

    assert str(exc_info.value) == f"The file '{path}' is not a valid SQLite database file."


@pytest.mark.parametrize(
    "token, expected_result, raises_exception",
    [
        ("valid_token_123", "valid_token_123", False),  # 合法token
        ("invalid token", None, True),
        ("invalid@token", None, True),
        (12345, None, True),
    ]
)
def test_check_token_valid(token, expected_result, raises_exception):
    if raises_exception:
        with pytest.raises(argparse.ArgumentTypeError):
            visual.check_token_valid(token)
    else:
        assert visual.check_token_valid(token) == expected_result


@pytest.mark.parametrize(
    "url, expected_result, raises_exception",
    [
        ("http://example.com", "http://example.com", False),  # 合法HTTP URL
        ("https://example.com", "https://example.com", False),  # 合法HTTPS URL
        ("example.com", None, True),
        ("http://", None, True),
    ]
)
def test_check_url_valid(url, expected_result, raises_exception):
    if raises_exception:
        with pytest.raises(argparse.ArgumentTypeError):
            visual.check_url_valid(url)
    else:
        assert visual.check_url_valid(url) == expected_result
