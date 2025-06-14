# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import unittest
import argparse
import os
import sqlite3
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock
import shutil
import pytest
import pandas as pd
from ms_service_profiler.utils.error import DatabaseError
from ms_service_profiler.utils.file_open_check import FileStat
from ms_service_profiler.utils.check.rule import Rule

# 测试目标模块
from ms_service_profiler.exporters.utils import (
    create_sqlite_db,
    add_table_into_visual_db,
    save_dataframe_to_csv,
    check_input_path_valid,
    check_output_path_valid,
    visual_db_fp,
    db_write_lock,
)


@pytest.fixture
def cleanup_db_file():
    """测试后清理数据库文件"""
    global visual_db_fp
    yield
    if os.path.exists(visual_db_fp):
        os.remove(visual_db_fp)
    visual_db_fp = ''


@pytest.fixture
def sample_dataframe():
    """提供一个示例DataFrame"""
    return pd.DataFrame({
        'col1': [1, 2, 3],
        'col2': ['a', 'b', 'c']
    })


def test_create_sqlite_db_success(tmpdir, cleanup_db_file):
    """测试成功创建SQLite数据库"""
    output_dir = os.path.join(os.getcwd(), "output_test")
    os.makedirs(output_dir, exist_ok=True)
    os.chmod(output_dir, 0o740)
    create_sqlite_db(str(output_dir))
    db_fp = Path(output_dir, 'profiler.db')
    conn = sqlite3.connect(db_fp)
    conn.close()
    assert os.path.exists(str(db_fp))


def test_add_table_into_visual_db_failure(tmpdir, sample_dataframe, cleanup_db_file):
    try:
        """测试添加表到SQLite数据库失败"""
        output_dir = tmpdir.mkdir("test_output")
        create_sqlite_db(str(output_dir))

        with patch('pandas.DataFrame.to_sql', side_effect=Exception("Insert failed")):
            with pytest.raises(DatabaseError, match="Cannot update sqlite database."):
                add_table_into_visual_db(sample_dataframe, 'test_table')
    finally:
        # 清理
        shutil.rmtree(output_dir)


def test_save_dataframe_to_csv_success(tmpdir, sample_dataframe):
    try:
        """测试成功保存DataFrame到CSV文件"""
        output_dir = os.path.join(os.getcwd(), "output_test")
        os.makedirs(output_dir, exist_ok=True)
        os.chmod(output_dir, 0o740)
        file_name = "test.csv"
        save_dataframe_to_csv(sample_dataframe, str(output_dir), file_name)

        file_path = os.path.join(str(output_dir), file_name)
        assert os.path.exists(file_path)
        df = pd.read_csv(file_path)
        assert df.equals(sample_dataframe)
    finally:
        # 清理
        shutil.rmtree(output_dir)


def test_save_dataframe_to_csv_none_output(sample_dataframe):
    """测试output为None时是否跳过保存"""
    save_dataframe_to_csv(sample_dataframe, None, "test.csv")
    # 无异常即为通过


def test_check_input_path_valid_success(tmpdir):
    """测试输入路径验证成功"""
    test_dir = tmpdir.mkdir("test_input")
    os.chmod(test_dir, 0o755)
    result = check_input_path_valid(str(test_dir))
    assert result == str(test_dir)


def test_check_output_path_valid_success(tmpdir):
    """测试输出路径验证成功"""
    test_dir = tmpdir.mkdir("test_output")
    result = check_output_path_valid(str(test_dir))
    assert result == os.path.abspath(str(test_dir))


def test_check_output_path_valid_create_dir(tmpdir):
    """测试输出路径不存在时自动创建"""
    test_dir = os.path.join(str(tmpdir), "new_dir")
    result = check_output_path_valid(test_dir)
    assert os.path.exists(test_dir)
    assert result == os.path.abspath(test_dir)


@unittest.skipIf(os.getuid() == 0, "root can write anything")
def test_check_output_path_valid_failure_not_writable(tmpdir):
    """测试输出路径不可写时的失败"""
    test_dir = tmpdir.mkdir("test_output")
    os.chmod(str(test_dir), 0o444)  # 只读权限

    with pytest.raises(argparse.ArgumentTypeError, match="File is not writable"):
        check_output_path_valid(str(test_dir))

