# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import argparse
import pandas as pd
import numpy as np
import subprocess  # <-- 新增：用于 mock subprocess 异常

# 正确导入路径（不含 is_valid_ascend_pt_path）
from ms_service_profiler.ms_service_profiler_ext.compare import (
    read_sql_from_given_path,
    validate_and_clean_df,
    compute_stats,
    compute_comparison,
    main,
    parse_args,
    _find_ascend_pt_dirs,
    _extract_prof_number,
    extract_device_to_ascend_pt_map,
    match_ascend_pt_paths_by_device
)


class TestCompareToolHighCoverage(unittest.TestCase):

    # -----------------------------
    # 1. read_sql_from_given_path
    # -----------------------------
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.DBDataSource')
    def test_read_sql_from_given_path_success(self, mock_db):
        df1 = pd.DataFrame({'name': ['a'], 'during_time': [10]})
        df2 = pd.DataFrame({'name': ['b'], 'during_time': [20]})
        mock_db.process.side_effect = [
            {'tx_data_df': df1},
            {'tx_data_df': df2}
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_dir = os.path.join(tmpdir, "Trace_Service")
            os.makedirs(trace_dir, exist_ok=True)

            db1 = os.path.join(trace_dir, "1.db")
            db2 = os.path.join(trace_dir, "2.db")
            open(db1, 'w').close()
            open(db2, 'w').close()

            result = read_sql_from_given_path(tmpdir)
            self.assertEqual(len(result), 2)
            self.assertIn('name', result.columns)

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.DBDataSource')
    def test_read_sql_from_given_path_no_valid_data(self, mock_db):
        mock_db.process.return_value = {'tx_data_df': pd.DataFrame()}
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "empty.db")
            open(db, 'w').close()
            result = read_sql_from_given_path(tmpdir)
            self.assertTrue(result.empty)

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.DBDataSource')
    def test_read_sql_from_given_path_exception_handling(self, mock_db):
        mock_db.process.side_effect = Exception("DB error")
        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "bad.db")
            open(db, 'w').close()
            result = read_sql_from_given_path(tmpdir)
            self.assertTrue(result.empty)

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.os.walk')
    def test_read_sql_from_given_path_no_db_files(self, mock_walk):
        mock_walk.return_value = [('.', [], ['a.txt', 'b.log'])]
        result = read_sql_from_given_path("/fake")
        self.assertTrue(result.empty)

    # -----------------------------
    # 2. validate_and_clean_df
    # -----------------------------
    def test_validate_and_clean_df_normal(self):
        df = pd.DataFrame({
            'name': ['x', None, 'y'],
            'during_time': [1, 2, 3]
        })
        cleaned = validate_and_clean_df(df, "Test")
        self.assertEqual(len(cleaned), 2)
        self.assertListEqual(list(cleaned['name']), ['x', 'y'])

    def test_validate_and_clean_df_empty_input(self):
        cleaned = validate_and_clean_df(pd.DataFrame(), "Test")
        self.assertTrue(cleaned.empty)

    def test_validate_and_clean_df_missing_name_column(self):
        df = pd.DataFrame({'during_time': [1, 2]})
        cleaned = validate_and_clean_df(df, "Test")
        self.assertTrue(cleaned.empty)

    def test_validate_and_clean_df_all_name_nan(self):
        df = pd.DataFrame({'name': [None, pd.NA], 'during_time': [1, 2]})
        cleaned = validate_and_clean_df(df, "Test")
        self.assertTrue(cleaned.empty)

    # -----------------------------
    # 3. compute_stats
    # -----------------------------
    def test_compute_stats_single_row(self):
        df = pd.DataFrame({'name': ['op'], 'during_time': [100]})
        stats = compute_stats(df, 'X')
        self.assertEqual(stats.loc['op', 'X-AVG'], 100.0)
        self.assertEqual(stats.loc['op', 'X-P50'], 100.0)
        self.assertEqual(stats.loc['op', 'X-P90'], 100.0)

    def test_compute_stats_multiple_same_name(self):
        df = pd.DataFrame({
            'name': ['op'] * 3,
            'during_time': [10, 20, 30]
        })
        stats = compute_stats(df, 'Y')
        self.assertAlmostEqual(stats.loc['op', 'Y-AVG'], 20.0)
        self.assertAlmostEqual(stats.loc['op', 'Y-P50'], 20.0)
        self.assertAlmostEqual(stats.loc['op', 'Y-P90'], 28.0)

    def test_compute_stats_empty_df(self):
        df = pd.DataFrame({'name': [], 'during_time': []})
        stats = compute_stats(df, 'Z')
        self.assertTrue(stats.empty)

    def test_compute_stats_during_time_has_nan(self):
        df = pd.DataFrame({
            'name': ['a', 'a'],
            'during_time': [10, np.nan]
        })
        stats = compute_stats(df, 'W')
        self.assertEqual(stats.loc['a', 'W-AVG'], 10.0)
        self.assertEqual(stats.loc['a', 'W-P50'], 10.0)
        self.assertEqual(stats.loc['a', 'W-P90'], 10.0)

    # -----------------------------
    # 4. compute_comparison —— 核心逻辑测试
    # -----------------------------
    def test_compute_comparison_full_merge(self):
        input_stats = pd.DataFrame({
            'Input-AVG': [20.0],
            'Input-P50': [20.0],
            'Input-P90': [28.0]
        }, index=pd.Index(['op1'], name='name'))

        golden_stats = pd.DataFrame({
            'Golden-AVG': [10.0],
            'Golden-P50': [10.0],
            'Golden-P90': [18.0]
        }, index=pd.Index(['op1'], name='name'))

        result = compute_comparison(input_stats, golden_stats)
        self.assertEqual(result.iloc[0]['DIFF-AVG'], 10.0)      # Input - Golden = 20 - 10
        self.assertAlmostEqual(result.iloc[0]['RDIFF-AVG(%)'], 100.0, places=2)  # (10)/10 * 100 = 100%
        self.assertEqual(result.iloc[0]['name'], 'op1')

    def test_compute_comparison_partial_overlap(self):
        input_stats = pd.DataFrame({
            'Input-AVG': [10.0],
            'Input-P50': [10.0],
            'Input-P90': [10.0]
        }, index=pd.Index(['op1'], name='name'))
        golden_stats = pd.DataFrame({
            'Golden-AVG': [20.0],
            'Golden-P50': [20.0],
            'Golden-P90': [20.0]
        }, index=pd.Index(['op2'], name='name'))

        result = compute_comparison(input_stats, golden_stats)
        self.assertEqual(len(result), 2)
        names = set(result['name'])
        self.assertIn('op1', names)
        self.assertIn('op2', names)

        df_indexed = result.set_index('name')
        # op1: golden 缺失
        self.assertTrue(pd.isna(df_indexed.loc['op1']['Golden-AVG']))
        self.assertTrue(pd.isna(df_indexed.loc['op1']['RDIFF-AVG(%)']))
        # op2: input 缺失
        self.assertTrue(pd.isna(df_indexed.loc['op2']['Input-AVG']))
        self.assertTrue(pd.isna(df_indexed.loc['op2']['RDIFF-AVG(%)']))

    def test_compute_comparison_empty_inputs(self):
        empty = pd.DataFrame()
        result = compute_comparison(empty, empty)
        expected_cols = [
            'name',
            'Golden-AVG', 'Golden-P50', 'Golden-P90',
            'Input-AVG', 'Input-P50', 'Input-P90',
            'DIFF-AVG', 'DIFF-P50', 'DIFF-P90',
            'RDIFF-AVG(%)', 'RDIFF-P50(%)', 'RDIFF-P90(%)'
        ]
        self.assertTrue(result.empty)
        self.assertListEqual(list(result.columns), expected_cols)

    def test_compute_comparison_one_empty(self):
        input_stats = pd.DataFrame({
            'Input-AVG': [10.0],
            'Input-P50': [10.0],
            'Input-P90': [10.0]
        }, index=pd.Index(['x'], name='name'))
        empty = pd.DataFrame()
        result = compute_comparison(input_stats, empty)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['name'], 'x')
        self.assertTrue(pd.isna(result.iloc[0]['Golden-AVG']))
        self.assertTrue(pd.isna(result.iloc[0]['RDIFF-AVG(%)']))

    def test_compute_comparison_rounding(self):
        input_stats = pd.DataFrame({
            'Input-AVG': [1.234567],
            'Input-P50': [1.234567],
            'Input-P90': [1.234567]
        }, index=pd.Index(['x'], name='name'))
        golden_stats = pd.DataFrame({
            'Golden-AVG': [1.0],
            'Golden-P50': [1.0],
            'Golden-P90': [1.0]
        }, index=pd.Index(['x'], name='name'))
        result = compute_comparison(input_stats, golden_stats)
        self.assertAlmostEqual(result.iloc[0]['DIFF-AVG'], 0.23, places=2)
        self.assertAlmostEqual(result.iloc[0]['RDIFF-AVG(%)'], 23.46, places=2)  # (0.234567/1)*100 ≈ 23.46

    def test_compute_comparison_rdiff_nan_cases(self):
        # Golden is zero
        input_stats = pd.DataFrame({'Input-AVG': [10.0]}, index=pd.Index(['op1'], name='name'))
        golden_stats = pd.DataFrame({'Golden-AVG': [0.0]}, index=pd.Index(['op1'], name='name'))
        result = compute_comparison(input_stats, golden_stats)
        self.assertTrue(pd.isna(result.iloc[0]['RDIFF-AVG(%)']))

        # Golden is NaN
        golden_stats_nan = pd.DataFrame({'Golden-AVG': [np.nan]}, index=pd.Index(['op2'], name='name'))
        result2 = compute_comparison(input_stats, golden_stats_nan)
        self.assertTrue(pd.isna(result2.iloc[0]['RDIFF-AVG(%)']))

        # Input is NaN
        input_stats_nan = pd.DataFrame({'Input-AVG': [np.nan]}, index=pd.Index(['op3'], name='name'))
        golden_stats_10 = pd.DataFrame({'Golden-AVG': [10.0]}, index=pd.Index(['op3'], name='name'))
        result3 = compute_comparison(input_stats_nan, golden_stats_10)
        self.assertTrue(pd.isna(result3.iloc[0]['RDIFF-AVG(%)']))

        # Input=0, Golden=10 → RDIFF = (0-10)/10 = -1.0 → -100%
        input_zero = pd.DataFrame({'Input-AVG': [0.0]}, index=pd.Index(['op4'], name='name'))
        golden_10 = pd.DataFrame({'Golden-AVG': [10.0]}, index=pd.Index(['op4'], name='name'))
        result4 = compute_comparison(input_zero, golden_10)
        self.assertAlmostEqual(result4.iloc[0]['RDIFF-AVG(%)'], -100.0, places=2)

    # -----------------------------
    # 5. parse_args
    # -----------------------------
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.argparse.ArgumentParser.parse_args')
    def test_parse_args_default(self, mock_parse):
        mock_parse.return_value = argparse.Namespace(
            input_path='/in',
            golden_path='/gold',
            output_path='/out',
            log_level='info'
        )
        args = parse_args()
        self.assertEqual(args.input_path, '/in')
        self.assertEqual(args.log_level, 'info')

    # -----------------------------
    # 6. main (integration)
    # -----------------------------
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.save_dataframe_to_csv')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.read_sql_from_given_path')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.set_log_level')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.parse_args')
    def test_main_success(self, mock_parse_args, mock_set_log, mock_read, mock_save):
        df = pd.DataFrame({'name': ['test'], 'during_time': [100]})
        mock_read.return_value = df
        mock_parse_args.return_value = MagicMock(
            input_path='/in',
            golden_path='/gold',
            output_path='/out',
            log_level='info'
        )

        main()
        self.assertEqual(mock_read.call_count, 2)
        mock_save.assert_called_once()

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.read_sql_from_given_path')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.parse_args')
    def test_main_empty_input(self, mock_parse_args, mock_read):
        mock_read.return_value = pd.DataFrame()
        mock_parse_args.return_value = MagicMock(
            input_path='/in',
            golden_path='/gold',
            output_path='/out',
            log_level='info'
        )
        main()
        self.assertEqual(mock_read.call_count, 1)

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.read_sql_from_given_path')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.parse_args')
    def test_main_empty_golden(self, mock_parse_args, mock_read):
        input_df = pd.DataFrame({'name': ['a'], 'during_time': [1]})
        mock_read.side_effect = [input_df, pd.DataFrame()]
        mock_parse_args.return_value = MagicMock(
            input_path='/in',
            golden_path='/gold',
            output_path='/out',
            log_level='info'
        )
        main()
        self.assertEqual(mock_read.call_count, 2)

    # -----------------------------
    # 7. Edge cases
    # -----------------------------
    def test_compute_stats_with_zero_and_negative(self):
        df = pd.DataFrame({
            'name': ['op'] * 3,
            'during_time': [-10, 0, 10]
        })
        stats = compute_stats(df, 'T')
        self.assertAlmostEqual(stats.loc['op', 'T-AVG'], 0.0)
        self.assertAlmostEqual(stats.loc['op', 'T-P50'], 0.0)
        self.assertAlmostEqual(stats.loc['op', 'T-P90'], 8.0)


    def test_find_ascend_pt_dirs_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "a_ascend_pt"), exist_ok=True)
            os.makedirs(os.path.join(tmpdir, "b_ascend_pt"), exist_ok=True)
            os.makedirs(os.path.join(tmpdir, "regular_dir"), exist_ok=True)
            result = _find_ascend_pt_dirs(tmpdir)
            expected = sorted([
                os.path.join(tmpdir, "a_ascend_pt"),
                os.path.join(tmpdir, "b_ascend_pt")
            ])
            self.assertEqual(result, expected)

    def test_find_ascend_pt_dirs_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "regular"), exist_ok=True)
            result = _find_ascend_pt_dirs(tmpdir)
            self.assertEqual(result, [])

    def test_find_ascend_pt_dirs_nonexistent_parent(self):
        result = _find_ascend_pt_dirs("/non/existent/path")
        self.assertEqual(result, [])

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.os.listdir')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.os.path.isdir')
    def test_match_ascend_pt_paths_by_device_device_match(self, mock_isdir, mock_listdir):
        def fake_listdir(path):
            if 'input' in path:
                return ['msprof_1_ascend_pt']
            elif 'golden' in path:
                return ['msprof_2_ascend_pt']
            elif 'msprof_1_ascend_pt' in path:
                return ['PROF_100_device_0']
            elif 'msprof_2_ascend_pt' in path:
                return ['PROF_100_device_0']
            elif 'PROF_100_device_0' in path:
                return ['device_0']
            return []

        mock_listdir.side_effect = fake_listdir
        mock_isdir.return_value = True

        input_pt, golden_pt = match_ascend_pt_paths_by_device("/input", "/golden")
        self.assertIn("msprof_1_ascend_pt", input_pt)
        self.assertIn("msprof_2_ascend_pt", golden_pt)

    def test_match_ascend_pt_paths_by_device_fallback_to_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_root = os.path.join(tmpdir, "input")
            golden_root = os.path.join(tmpdir, "golden")
            os.makedirs(input_root, exist_ok=True)
            os.makedirs(golden_root, exist_ok=True)

            input_pt = os.path.join(input_root, "msprof_1_ascend_pt")
            golden_pt = os.path.join(golden_root, "msprof_2_ascend_pt")
            os.makedirs(input_pt, exist_ok=True)
            os.makedirs(golden_pt, exist_ok=True)

            inp, gold = match_ascend_pt_paths_by_device(input_root, golden_root)
            self.assertEqual(inp, input_pt)
            self.assertEqual(gold, golden_pt)


    @patch('ms_service_profiler.ms_service_profiler_ext.compare.subprocess')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.read_sql_from_given_path')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.save_dataframe_to_csv')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.set_log_level')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.parse_args')
    def test_main_operator_invalid_paths_skipped(self, mock_parse, mock_set_log, mock_save, mock_read, mock_subprocess):
        args = MagicMock()
        args.input_path = "/input"
        args.golden_path = "/golden"
        args.output_path = "/output"
        args.log_level = "info"
        mock_parse.return_value = args

        with patch('ms_service_profiler.ms_service_profiler_ext.compare.match_ascend_pt_paths_by_device') as mock_match:
            mock_match.return_value = ("", "")  # Invalid paths

            df = pd.DataFrame({'name': ['op'], 'during_time': [10]})
            mock_read.return_value = df

            main()

            # subprocess.run should NOT be called because paths are empty
            mock_subprocess.assert_not_called()

            self.assertEqual(mock_read.call_count, 2)
            mock_save.assert_called_once()


    @patch('ms_service_profiler.ms_service_profiler_ext.compare.os.listdir')
    def test_find_ascend_pt_dirs_permission_error(self, mock_listdir):
        mock_listdir.side_effect = OSError("Permission denied")
        result = _find_ascend_pt_dirs("/some/dir")
        self.assertEqual(result, [])

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.os.listdir')
    def test_extract_device_map_inner_exception(self, mock_listdir):
        mock_listdir.side_effect = [['PROF_1_device'], OSError("Disk error")]
        result = extract_device_to_ascend_pt_map("/root")
        self.assertIsInstance(result, dict)

    def test_match_paths_golden_empty_fallback(self):
        with patch('ms_service_profiler.ms_service_profiler_ext.compare._find_ascend_pt_dirs') as mock_find:
            mock_find.side_effect = lambda x: ['/input/ascend_pt'] if 'input' in x else []
            input_pt, golden_pt = match_ascend_pt_paths_by_device("/input", "/golden")
            self.assertEqual(input_pt, "/input/ascend_pt")
            self.assertEqual(golden_pt, "")

    def test_read_sql_no_trace_service(self):
        df = read_sql_from_given_path("/invalid/path")
        self.assertTrue(df.empty)

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.os.listdir')
    def test_read_sql_no_db_files(self, mock_listdir):
        mock_listdir.return_value = ['log.txt']
        with patch('ms_service_profiler.ms_service_profiler_ext.compare.os.path.isdir', return_value=True):
            df = read_sql_from_given_path("/valid/path")
            self.assertTrue(df.empty)

    def test_validate_empty_df(self):
        empty_df = pd.DataFrame()
        result = validate_and_clean_df(empty_df, "Test")
        self.assertTrue(result.empty)

    def test_validate_missing_name_column(self):
        df = pd.DataFrame({'id': [1]})
        result = validate_and_clean_df(df, "Test")
        self.assertTrue(result.empty)

    def test_compute_comparison_both_empty(self):
        empty_stats = pd.DataFrame()
        result = compute_comparison(empty_stats, empty_stats)
        self.assertIn('name', result.columns)
        self.assertTrue(result.empty)

    @patch('ms_service_profiler.ms_service_profiler_ext.compare.read_sql_from_given_path')
    @patch('ms_service_profiler.ms_service_profiler_ext.compare.parse_args')
    def test_main_input_empty(self, mock_parse, mock_read):
        args = MagicMock()
        args.input_path = "/input"
        args.golden_path = "/golden"
        args.output_path = "/out"
        args.log_level = "info"
        mock_parse.return_value = args
        mock_read.return_value = pd.DataFrame()  # 空输入

        main()

    def test_extract_prof_number_success(self):
        """测试 PROF_数字_ 格式能正确提取数字"""
        assert _extract_prof_number("PROF_123_device") == 123
        assert _extract_prof_number("some_prefix_PROF_456_suffix") == 456
        assert _extract_prof_number("PROF_0_abc") == 0

    def test_extract_prof_number_no_match(self):
        """测试无法匹配时返回 float('inf')"""
        assert _extract_prof_number("no_pattern_here") == float('inf')
        assert _extract_prof_number("PROF_abc_") == float('inf')  # 非数字
        assert _extract_prof_number("PROF_123") == float('inf')  # 缺少尾部 '_'
        assert _extract_prof_number("PROF__device") == float('inf')  # 空数字
        assert _extract_prof_number("") == float('inf')

    def test_extract_device_to_ascend_pt_map_basic(self):
        """基本场景：一个 PROF 目录 + 一个 device_数字"""
        with patch('ms_service_profiler.ms_service_profiler_ext.compare.os.listdir') as mock_listdir, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.os.path.isdir', return_value=True), \
                patch('ms_service_profiler.ms_service_profiler_ext.compare._find_ascend_pt_dirs',
                      return_value=['/root/ascend_pt']), \
                patch('ms_service_profiler.ms_service_profiler_ext.compare._extract_prof_number', return_value=123):
            # 第一次 os.listdir('/root/ascend_pt') → ['PROF_123_xxx']
            # 第二次 os.listdir('/root/ascend_pt/PROF_123_xxx') → ['device_456']
            mock_listdir.side_effect = [
                ['PROF_123_xxx'],
                ['device_456']
            ]

            result = extract_device_to_ascend_pt_map("/root")
            assert result == {456: '/root/ascend_pt'}

    def test_extract_device_to_ascend_pt_map_multiple_devices(self):
        """一个 PROF 目录包含多个合法 device"""
        with patch('ms_service_profiler.ms_service_profiler_ext.compare.os.listdir') as mock_listdir, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.os.path.isdir', return_value=True), \
                patch('ms_service_profiler.ms_service_profiler_ext.compare._find_ascend_pt_dirs',
                      return_value=['/root/ascend_pt']), \
                patch('ms_service_profiler.ms_service_profiler_ext.compare._extract_prof_number', return_value=100):
            mock_listdir.side_effect = [
                ['PROF_100_run'],
                ['device_0', 'device_1', 'device_invalid', 'device_99']
            ]

            result = extract_device_to_ascend_pt_map("/root")
            # 只保留 device_数字 的项
            assert result == {0: '/root/ascend_pt', 1: '/root/ascend_pt', 99: '/root/ascend_pt'}

    def test_extract_device_to_ascend_pt_map_skip_non_digit_device(self):
        """跳过非数字后缀的 device_"""
        with patch('ms_service_profiler.ms_service_profiler_ext.compare.os.listdir') as mock_listdir, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.os.path.isdir', return_value=True), \
                patch('ms_service_profiler.ms_service_profiler_ext.compare._find_ascend_pt_dirs',
                      return_value=['/root/pt']), \
                patch('ms_service_profiler.ms_service_profiler_ext.compare._extract_prof_number', return_value=200):
            mock_listdir.side_effect = [
                ['PROF_200_exp'],
                ['device_', 'device_abc', 'device_12x', 'device_789']  # 只有 device_789 合法
            ]

            result = extract_device_to_ascend_pt_map("/root")
            assert result == {789: '/root/pt'}

    def test_match_paths_no_device_overlap_fallback_to_min(self):
        """
        测试：golden 和 input 都有设备，但设备编号无交集 → 触发 fallback 到最小设备号逻辑
        """
        # 模拟 extract_device_to_ascend_pt_map 返回值
        with patch(
                'ms_service_profiler.ms_service_profiler_ext.compare.extract_device_to_ascend_pt_map') as mock_extract, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare._find_ascend_pt_dirs') as mock_find:
            # golden 有 device 1,2；input 有 device 3,4 → 无交集
            mock_extract.side_effect = [
                {3: "/input/pt3", 4: "/input/pt4"},  # input_map
                {1: "/golden/pt1", 2: "/golden/pt2"}  # golden_map
            ]

            # 当 input_map 为空时才调用 _find_ascend_pt_dirs，但这里 input_map 非空，所以不会调用
            # 但为了安全，mock 它返回空
            mock_find.return_value = []

            input_pt, golden_pt = match_ascend_pt_paths_by_device("/input", "/golden")

            # 预期：golden 选最小设备 1 → "/golden/pt1"
            #       input 选最小设备 3 → "/input/pt3"
            assert input_pt == "/input/pt3"
            assert golden_pt == "/golden/pt1"

    def test_main_calls_subprocess_when_paths_found(self):
        """测试 main() 在找到 ascend_pt 路径时调用 subprocess.run"""
        with patch('ms_service_profiler.ms_service_profiler_ext.compare.parse_args') as mock_parse, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.set_log_level'), \
                patch(
                    'ms_service_profiler.ms_service_profiler_ext.compare.match_ascend_pt_paths_by_device') as mock_match, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.logger'), \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.subprocess.run') as mock_run, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.read_sql_from_given_path') as mock_read, \
                patch('ms_service_profiler.ms_service_profiler_ext.compare.save_dataframe_to_csv'):
            # 模拟命令行参数
            args = MagicMock()
            args.input_path = "/input"
            args.golden_path = "/golden"
            args.output_path = "/output"
            args.log_level = "info"
            mock_parse.return_value = args

            # 关键：让 match 返回非空路径 → 触发 subprocess
            mock_match.return_value = ("/input/pt", "/golden/pt")

            # 模拟 span 数据非空（避免提前 return）
            mock_read.return_value = pd.DataFrame({'name': ['op'], 'during_time': [10]})

            # 调用 main
            from ms_service_profiler.ms_service_profiler_ext.compare import main
            main()

            # 断言 subprocess.run 被调用
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            assert called_cmd == [
                "msprof-analyze", "compare",
                "-d", "/input/pt",
                "-bp", "/golden/pt",
                "--output_path", "/output"
            ]


if __name__ == '__main__':
    unittest.main()