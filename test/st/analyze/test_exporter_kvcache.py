# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import sqlite3
import unittest
import os
import glob
import argparse
from pathlib import Path
import pandas as pd
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData



class TestExporterKVCacheData(unittest.TestCase):
    OUTPUT_PATH = "test_output"  # 测试输出目录
    CSV_FILE_NAME = "kvcache.csv"
    DB_FILE_NAME = "profiler.db"

    @classmethod
    def setUpClass(cls):
        # 创建输出目录
        Path(cls.OUTPUT_PATH).mkdir(parents=True, exist_ok=True)

        # 初始化 ExporterKVCacheData
        args = argparse.Namespace(output_path=cls.OUTPUT_PATH)
        ExporterKVCacheData.initialize(args)

        # 模拟输入数据
        data = {
            'tx_data_df': pd.DataFrame({
                'domain': ['KVCache', 'KVCache', 'KVCache', 'KVCache'],
                'rid': [0, 1, 2, 3],
                'start_time': ['1735124796367194', '1735124796367220', '1735124796367233', '1735124796367242'],
                'end_time': ['1735124796367194', '1735124796367220', '1735124796367233', '1735124796367242'],
                'name': ['Allocate', 'Free', 'AppendSlot', 'AppendSlot'],
                'deviceBlock=': [1978, 1977, 1976, 1975],
                'during_time': ['0', '0', '0', '0'],
                'start_datetime': ['2024-12-25', '2024-12-25', '2024-12-25', '2024-12-25']
            })
        }

        # 执行导出操作
        ExporterKVCacheData.export(data)

    @classmethod
    def tearDownClass(cls):
        # 清理测试输出目录
        for file in glob.glob(f"{cls.OUTPUT_PATH}/*"):
            os.remove(file)
        os.rmdir(cls.OUTPUT_PATH)

    def test_csv_file_generated(self):
        # 检查 CSV 文件是否生成
        csv_file = os.path.join(self.OUTPUT_PATH, self.CSV_FILE_NAME)
        self.assertTrue(os.path.exists(csv_file), f"{self.CSV_FILE_NAME} 文件未生成")

    def test_db_file_generated(self):
        # 检查 SQLite 数据库文件是否生成
        db_file = os.path.join(self.OUTPUT_PATH, self.DB_FILE_NAME)
        self.assertTrue(os.path.exists(db_file), f"{self.DB_FILE_NAME} 文件未生成")

    def test_csv_file_content(self):
        # 检查 CSV 文件内容是否符合预期
        csv_file = os.path.join(self.OUTPUT_PATH, self.CSV_FILE_NAME)
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            # 检查是否包含预期的列
            expected_columns = ['domain', 'rid', 'start_time(microsecond)', 'end_time(microsecond)',
                               'name', 'device_kvcache_left', 'during_time(microsecond)']
            self.assertListEqual(list(df.columns), expected_columns, "CSV 文件列名不符合预期")
        else:
            self.fail(f"{self.CSV_FILE_NAME} 文件未生成")

    def test_db_file_content(self):
        # 检查 SQLite 数据库文件是否符合预期
        db_file = os.path.join(self.OUTPUT_PATH, self.DB_FILE_NAME)
        if os.path.exists(db_file):
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            cursor.execute('PRAGMA table_info("kvcache")')
            columns = cursor.fetchall()

            # 预期列名
            expected_columns = [
                ('rid', 'INTEGER'),
                ('name', 'TEXT'),
                ('real_start_time', 'TEXT'),
                ('device_kvcache_left', 'INTEGER'),
                ('kvcache_usage_rate', 'REAL')
            ]

            for i, (_, name, type_, *_) in enumerate(columns):
                self.assertEqual(name, expected_columns[i][0], f"列名 {name} 不符合预期")
                self.assertEqual(type_, expected_columns[i][1], f"列 {name} 的数据类型 {type_} 不符合预期")

                # 关闭数据库连接
            conn.close()
        else:
            self.fail(f"{self.DB_FILE_NAME} 文件未生成")


if __name__ == "__main__":
    unittest.main()