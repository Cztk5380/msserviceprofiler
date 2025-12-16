# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import MagicMock, patch, mock_open
import psutil
import multiprocessing as mp
import math
import json
from collections import defaultdict
from ms_service_profiler.utils.trace_to_db import (
    # 常量
    NS_PER_US,
    DB_CACHE_SIZE,
    TRACE_TABLE_DEFINITIONS,
    UPDATE_PROCESS_NAME_SQL,
    UPDATE_THREAD_NAME_SQL,
    UPDATE_PROCESS_LABLE_SQL,
    UPDATE_PROCESS_SORTINDEX_SQL,
    UPDATE_THREAD_SORTINDEX_SQL,
    SIMULATION_UPDATE_PROCESS_NAME_SQL,
    SIMULATION_UPDATE_THREAD_NAME_SQL,
    UPDATA_SQL_TEMPLATES,
    MIN_PROCESSES,
    MAX_PROCESSES,
    MIN_CHUNK_SIZE,
    DEFAULT_BATCH_SIZE,



    # 函数
    convert_ts_to_ns,
    trans_trace_meta_data,
    trans_trace_slice_data,
    trans_trace_flow_data,
    trans_trace_counter_data,
    calculate_smart_process_config,
    write_all_data_smart,
    _calculate_batch_size,


    # 类
    TrackIdManager,
    ProcessTableManager,
    CacheTableManager,

    # 事件处理函数
    trans_trace_meta_event,
    write_to_process_thread_table,
    trans_trace_slice_event,
    trans_trace_counter_event,
    trans_trace_flow_event,
    trans_trace_event,
    save_cache_data_to_db,
    _write_data_batch,

)


# 单测代码
class TestTraceEvent(unittest.TestCase):

    def setUp(self):
        self.cursor = MagicMock()
        self.event = {
            'name': 'process_name',
            'tid': 1,
            'pid': 1,
            'args': {'name': 'test_process'},
            'ts': 100,
            'dur': 200,
            'ph': 'M'
        }


    def test_convert_ts_to_ns(self):
        self.assertEqual(convert_ts_to_ns(100), 100000)


    def test_trans_trace_meta_data(self):
        result = trans_trace_meta_data(self.event)
        self.assertEqual(result['name'], 'process_name')
        self.assertEqual(result['tid'], 1)
        self.assertEqual(result['pid'], 1)
        self.assertEqual(result['args_name'], 'test_process')


    def test_trans_trace_slice_data(self):
        self.event['ph'] = 'X'
        result = trans_trace_slice_data(self.event)
        self.assertEqual(result['ts'], 100000)
        self.assertEqual(result['dur'], 200000)
        self.assertEqual(result['name'], 'process_name')
        self.assertEqual(result['pid'], 1)


    def test_trans_trace_counter_data(self):
        self.event['ph'] = 'C'
        self.event['id'] = '1'  # 确保 cid 是字符串
        result = trans_trace_counter_data(self.event)
        self.assertEqual(result['ts'], 100000)  # 假设 ts 转换后的值
        self.assertEqual(result['name'], 'process_name')  # 检查名称是否正确拼接
        self.assertEqual(result['pid'], 1)
        self.assertEqual(result['tid'], 'process_name')
        self.assertEqual(result['cat'], None)  # 假设没有 cat 字段
        self.assertEqual(result['args'], json.dumps(self.event['args']))


    def test_trans_trace_flow_data(self):
        self.event['ph'] = 's'
        self.event['id'] = 1

        result = trans_trace_flow_data(self.event)

        # 验证返回值
        self.assertEqual(result['ts'], 100000)  # 假设 ts 转换后的值
        self.assertEqual(result['name'], 'process_name')
        self.assertEqual(result['pid'], 1)
        self.assertEqual(result['tid'], 1)
        self.assertEqual(result['cat'], None)
        self.assertEqual(result['flow_id'], 1)


    def test_trans_trace_meta_event(self):
        trans_trace_meta_event(self.event, self.cursor)
        self.cursor.execute.assert_called_once_with(UPDATE_PROCESS_NAME_SQL, (1, 'test_process'))


    def test_trans_trace_meta_event_process_name(self):
        self.event['name'] = "process_name"
        self.event['pid'] = 1
        self.event['args'] = {'name': 'test_process'}

        trans_trace_meta_event(self.event, self.cursor)

        expected_call = (
            UPDATE_PROCESS_NAME_SQL,
            (1, 'test_process')
        )
        self.cursor.execute.assert_called_with(*expected_call)


    def test_trans_trace_meta_event_thread_name(self):
        self.event['name'] = "thread_name"
        self.event['pid'] = 1
        self.event['tid'] = 1
        self.event['args'] = {'name': 'test_thread'}

        trans_trace_meta_event(self.event, self.cursor)

        track_id, _ = TrackIdManager.get_track_id(1, 1)
        expected_call = (
            UPDATE_THREAD_NAME_SQL,
            (track_id, 1, 1, 'test_thread')
        )
        self.cursor.execute.assert_called_with(*expected_call)


    def test_trans_trace_meta_event_process_labels(self):
        self.event['name'] = "process_labels"
        self.event['pid'] = 1
        self.event['args'] = {'labels': 'test_label'}

        trans_trace_meta_event(self.event, self.cursor)

        expected_call = (
            UPDATE_PROCESS_LABLE_SQL,
            (1, 'test_label')
        )
        self.cursor.execute.assert_called_with(*expected_call)


    def test_trans_trace_meta_event_process_sort_index(self):
        self.event['name'] = "process_sort_index"
        self.event['pid'] = 1
        self.event['args'] = {'sort_index': 10}

        trans_trace_meta_event(self.event, self.cursor)

        expected_call = (
            UPDATE_PROCESS_SORTINDEX_SQL,
            (1, 10)
        )
        self.cursor.execute.assert_called_with(*expected_call)

    def test_trans_trace_meta_event_thread_sort_index(self):
        self.event['name'] = "thread_sort_index"
        self.event['pid'] = 1
        self.event['tid'] = 1
        self.event['args'] = {'sort_index': 10}

        # 模拟数据库查询返回结果，表示记录已存在
        self.cursor.fetchone.return_value = (2,)  # 返回track_id=2

        trans_trace_meta_event(self.event, self.cursor)

        # 验证执行了更新操作
        expected_call = (
            UPDATE_THREAD_SORTINDEX_SQL,
            (2, 10)
        )
        self.cursor.execute.assert_called_with(*expected_call)

    def test_trans_trace_meta_event_unknown_name(self):
        self.event['name'] = "unknown_name"
        self.event['pid'] = 1
        self.event['args'] = {'name': 'test_process'}

        trans_trace_meta_event(self.event, self.cursor)

        # 验证没有调用 cursor.execute
        self.cursor.execute.assert_not_called()

    def test_write_to_process_thread_table(self):
        self.event['thread_sort_index'] = 1
        event_data = trans_trace_meta_data(self.event)
        with patch('ms_service_profiler.utils.trace_to_db.TrackIdManager.get_track_id', return_value=(2, True)):
            write_to_process_thread_table(event_data, 1, self.cursor)
            expected_call = (
                SIMULATION_UPDATE_THREAD_NAME_SQL,
                (2, 1, 1, 1, 1)  # (track_id, tid, pid, thread_name, thread_sort_index=1)
            )
            self.cursor.execute.assert_called_with(*expected_call)

    def test_trans_trace_slice_event(self):
        self.event['ph'] = 'X'
        self.event['thread_sort_index'] = 1
        with patch('ms_service_profiler.utils.trace_to_db.TrackIdManager.get_track_id', return_value=(2, True)):
            trans_trace_slice_event(self.event, self.cursor)
            expected_call = (
                SIMULATION_UPDATE_THREAD_NAME_SQL,
                (2, 1, 1, 1, 1)  # (track_id, tid, pid, thread_name, thread_sort_index=1)
            )
            self.cursor.execute.assert_called_with(*expected_call)

    def test_trans_trace_flow_event(self):
        self.event['ph'] = 's'
        with patch('ms_service_profiler.utils.trace_to_db.TrackIdManager.get_track_id', return_value=(2, True)):
            trans_trace_flow_event(self.event, 's', self.cursor)
            expected_call = (
                SIMULATION_UPDATE_THREAD_NAME_SQL,
                (2, 1, 1, 1, None)  # (track_id, tid, pid, thread_name, thread_sort_index)
            )
            self.cursor.execute.assert_called_with(*expected_call)


    def test_trans_trace_counter_event(self):
        self.event['ph'] = 'C'
        self.event['thread_sort_index'] = 1  # 确保 thread_sort_index 是整数 1
        trans_trace_counter_event(self.event, self.cursor)
        self.cursor.execute.assert_called_with(SIMULATION_UPDATE_THREAD_NAME_SQL,
                                               (1, 'process_name', 1, 'process_name', 1))


    def test_trans_trace_event_meta(self):
        self.event['ph'] = 'M'
        trans_trace_event(self.event, self.cursor)
        expected_call = (
            UPDATE_PROCESS_NAME_SQL,
            (1, 'test_process')
        )
        self.cursor.execute.assert_called_with(*expected_call)

    def test_trans_trace_event_slice(self):
        self.event['ph'] = 'X'
        with patch('ms_service_profiler.utils.trace_to_db.TrackIdManager.get_track_id', return_value=(2, True)):
            trans_trace_event(self.event, self.cursor)
            expected_call = (
                SIMULATION_UPDATE_THREAD_NAME_SQL,
                (2, 1, 1, 1, None)  # (track_id, tid, pid, thread_name, thread_sort_index)
            )
            self.cursor.execute.assert_called_with(*expected_call)

    def test_trans_trace_event_counter(self):
        self.event['ph'] = 'C'
        with patch('ms_service_profiler.utils.trace_to_db.TrackIdManager.get_track_id', return_value=(2, True)):
            trans_trace_event(self.event, self.cursor)
            expected_call = (
                SIMULATION_UPDATE_THREAD_NAME_SQL,
                (2, 'process_name', 1, 'process_name', None)  # (track_id, tid, pid, thread_name, thread_sort_index)
            )
            self.cursor.execute.assert_called_with(*expected_call)


    def test_trans_trace_event_flow(self):
        self.event['ph'] = 's'
        trans_trace_event(self.event, self.cursor)
        expected_call = (
            SIMULATION_UPDATE_THREAD_NAME_SQL,
            (2, 1, 1, 1, None)
        )
        self.cursor.execute.assert_called_with(*expected_call)


    def test_trans_trace_event_unknown(self):
        self.event['ph'] = 'Z'  # 未知的事件类型
        trans_trace_event(self.event, self.cursor)
        self.cursor.execute.assert_not_called()


    def test_save_cache_data_to_db(self):
        save_cache_data_to_db(self.cursor)
        self.cursor.executemany.assert_called()


class TestSmartProcessConfig(unittest.TestCase):

    def test_calculate_smart_process_config_small_data(self):
        """测试小数据量的配置计算"""
        with patch('ms_service_profiler.utils.trace_to_db.mp.cpu_count', return_value=4), \
                patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.total = 8 * 1024 ** 3  # 8GB
            mock_memory.return_value.available = 4 * 1024 ** 3  # 4GB available

            processes, chunk_size = calculate_smart_process_config(1000)

            # 验证进程数在合理范围内
            self.assertGreaterEqual(processes, MIN_PROCESSES)
            self.assertLessEqual(processes, MAX_PROCESSES)
            # 验证分块大小
            self.assertGreaterEqual(chunk_size, MIN_CHUNK_SIZE)

    def test_calculate_smart_process_config_large_data(self):
        """测试大数据量的配置计算"""
        with patch('ms_service_profiler.utils.trace_to_db.mp.cpu_count', return_value=8), \
                patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.total = 16 * 1024 ** 3  # 16GB
            mock_memory.return_value.available = 8 * 1024 ** 3  # 8GB available

            processes, chunk_size = calculate_smart_process_config(10000000)  # 1000万事件

            # 验证大数据量下的计算
            self.assertGreaterEqual(processes, MIN_PROCESSES)
            self.assertLessEqual(processes, MAX_PROCESSES)

    def test_calculate_smart_process_config_memory_limited(self):
        """测试内存受限的情况"""
        with patch('ms_service_profiler.utils.trace_to_db.mp.cpu_count', return_value=4), \
                patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.total = 4 * 1024 ** 3  # 4GB
            mock_memory.return_value.available = 1 * 1024 ** 3  # 1GB available（内存紧张）

            processes, chunk_size = calculate_smart_process_config(1000000)

            # 内存受限时进程数应该较小
            self.assertLessEqual(processes, 4)

    def test_calculate_smart_process_config_cpu_limited(self):
        """测试CPU受限的情况"""
        # 通过设置极高的内存和数据量限制，使CPU成为瓶颈
        with patch('ms_service_profiler.utils.trace_to_db.mp.cpu_count', return_value=2), \
                patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory') as mock_memory, \
                patch('ms_service_profiler.utils.trace_to_db.MEMORY_PER_PROCESS_MB', 1), \
                patch('ms_service_profiler.utils.trace_to_db.TARGET_EVENTS_PER_PROCESS', 1):
            mock_memory.return_value.total = 1000 * 1024 ** 3  # 大量内存
            mock_memory.return_value.available = 1000 * 1024 ** 3  # 大量可用内存

            processes, chunk_size = calculate_smart_process_config(1)  # 极小的数据量

            # 在内存和数据量都不是限制的情况下，CPU数量应该是限制因素
            self.assertLessEqual(processes, 4)

    def test_calculate_smart_process_config_chunk_size_adjustment(self):
        """测试分块大小调整逻辑"""
        with patch('ms_service_profiler.utils.trace_to_db.mp.cpu_count', return_value=4), \
                patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.total = 8 * 1024 ** 3
            mock_memory.return_value.available = 4 * 1024 ** 3

            # 模拟导致大分块的情况
            with patch('ms_service_profiler.utils.trace_to_db.TARGET_EVENTS_PER_PROCESS', 100), \
                    patch('ms_service_profiler.utils.trace_to_db.LARGE_CHUNK_THRESHOLD', 10), \
                    patch('ms_service_profiler.utils.trace_to_db.CHUNK_SIZE_BASELINE', 5):
                processes, chunk_size = calculate_smart_process_config(1000)

                # 验证分块大小调整逻辑被触发
                self.assertGreaterEqual(processes, MIN_PROCESSES)


class TestWriteAllDataSmart(unittest.TestCase):

    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    def test_write_all_data_smart_connection_failure(self):
        """测试数据库连接失败"""
        with patch('ms_service_profiler.utils.trace_to_db.get_db_connection', return_value=None), \
                patch('ms_service_profiler.utils.trace_to_db.logger') as mock_logger:
            write_all_data_smart({'slice': [], 'counter': [], 'flow': []})

            mock_logger.warning.assert_called_with("Failed to get database connection for final write")

    def test_write_all_data_smart_normal_case(self):
        """测试正常写入数据"""
        data_results = {
            'slice': [(100, 50, 'slice1', 1, 'cat1', {}, 'red', 150, None)],
            'counter': [('counter1', 1, 200, 'cat1', {})],
            'flow': [('flow1', 'flow1', 1, 300, 'cat1', 's')]
        }

        with patch('ms_service_profiler.utils.trace_to_db.get_db_connection', return_value=self.mock_conn), \
                patch('ms_service_profiler.utils.trace_to_db._calculate_batch_size', return_value=100), \
                patch('ms_service_profiler.utils.trace_to_db._write_data_batch') as mock_write_batch:
            write_all_data_smart(data_results)

            # 验证数据库优化设置
            expected_calls = [
                unittest.mock.call("PRAGMA journal_mode = WAL"),
                unittest.mock.call("PRAGMA cache_size = -100000"),
                unittest.mock.call("PRAGMA synchronous = NORMAL"),
                unittest.mock.call("PRAGMA temp_store = MEMORY")
            ]
            self.mock_cursor.execute.assert_has_calls(expected_calls)

            # 验证写入函数被调用
            self.assertEqual(mock_write_batch.call_count, 3)
            # 验证提交操作
            self.mock_conn.commit.assert_called()

    def test_write_all_data_smart_exception(self):
        """测试写入数据时发生异常"""
        with patch('ms_service_profiler.utils.trace_to_db.get_db_connection', return_value=self.mock_conn), \
                patch('ms_service_profiler.utils.trace_to_db._calculate_batch_size', side_effect=Exception("DB Error")), \
                patch('ms_service_profiler.utils.trace_to_db.logger') as mock_logger:
            write_all_data_smart({'slice': [], 'counter': [], 'flow': []})

            # 验证回滚操作
            self.mock_conn.rollback.assert_called()
            mock_logger.warning.assert_called()

    def test_write_all_data_smart_resource_cleanup(self):
        """测试资源清理"""
        with patch('ms_service_profiler.utils.trace_to_db.get_db_connection', return_value=self.mock_conn):
            write_all_data_smart({'slice': [], 'counter': [], 'flow': []})

            # 验证资源清理
            self.mock_cursor.close.assert_called()
            self.mock_conn.close.assert_called()


class TestCalculateBatchSize(unittest.TestCase):

    def test_calculate_batch_size_small_data(self):
        """测试小数据量的批次大小计算"""
        data_results = {
            'slice': [1] * 50000,  # 5万条记录
            'counter': [],
            'flow': []
        }

        batch_size = _calculate_batch_size(data_results)

        # 小数据量时批次大小应该较小
        self.assertLessEqual(batch_size, DEFAULT_BATCH_SIZE)

    def test_calculate_batch_size_large_data(self):
        """测试大数据量的批次大小计算"""
        data_results = {
            'slice': [1] * 2000000,  # 200万条记录
            'counter': [1] * 1000000,  # 100万条记录
            'flow': [1] * 500000  # 50万条记录
        }

        with patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.available = 8 * 1024 ** 3  # 8GB available

            batch_size = _calculate_batch_size(data_results)

            # 大数据量时批次大小应该较大
            self.assertGreaterEqual(batch_size, DEFAULT_BATCH_SIZE)

    def test_calculate_batch_size_low_memory(self):
        """测试低内存情况下的批次大小计算"""
        data_results = {
            'slice': [1] * 1000000,
            'counter': [1] * 500000,
            'flow': []
        }

        with patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.available = 1 * 1024 ** 3  # 1GB available（低内存）

            batch_size = _calculate_batch_size(data_results)

            # 低内存时批次大小应该较小
            self.assertLessEqual(batch_size, DEFAULT_BATCH_SIZE)

    def test_calculate_batch_size_memory_check_error(self):
        """测试内存检查失败时的批次大小计算"""
        data_results = {
            'slice': [1] * 100000,
            'counter': [],
            'flow': []
        }

        with patch('ms_service_profiler.utils.trace_to_db.psutil.virtual_memory',
                   side_effect=Exception("Memory error")), \
                patch('ms_service_profiler.utils.trace_to_db.logger') as mock_logger:
            batch_size = _calculate_batch_size(data_results)

            # 内存检查失败时使用默认批次大小
            self.assertEqual(batch_size, DEFAULT_BATCH_SIZE)
            mock_logger.debug.assert_called()


class TestWriteDataBatch(unittest.TestCase):

    def setUp(self):
        self.mock_cursor = MagicMock()

    def test_write_data_batch_empty_data(self):
        """测试空数据写入"""
        with patch('ms_service_profiler.utils.trace_to_db.logger') as mock_logger:
            _write_data_batch(self.mock_cursor, "slice", [], 100, "INSERT SQL")

            # 验证没有执行SQL
            self.mock_cursor.executemany.assert_not_called()
            mock_logger.debug.assert_called()

    def test_write_data_batch_single_batch(self):
        """测试单批次写入"""
        data = [(100, 50, 'slice1', 1, 'cat1', {}, 'red', 150, None)] * 50  # 50条记录
        batch_size = 100  # 大于数据量，只需一个批次

        _write_data_batch(self.mock_cursor, "slice", data, batch_size,
                          "INSERT INTO slice VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")

        # 验证executemany被调用一次
        self.mock_cursor.executemany.assert_called_once()

    def test_write_data_batch_multiple_batches(self):
        """测试多批次写入"""
        data = [(100, 50, 'slice1', 1, 'cat1', {}, 'red', 150, None)] * 250  # 250条记录
        batch_size = 100  # 需要3个批次

        with patch('ms_service_profiler.utils.trace_to_db.PROGRESS_REPORT_FREQUENCY', 1):  # 每批次都报告进度
            _write_data_batch(self.mock_cursor, "slice", data, batch_size,
                              "INSERT INTO slice VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")

        # 验证executemany被调用3次
        self.assertEqual(self.mock_cursor.executemany.call_count, 3)

    def test_write_data_batch_progress_report(self):
        """测试进度报告"""
        data = [(100, 50, 'slice1', 1, 'cat1', {}, 'red', 150, None)] * 300  # 300条记录
        batch_size = 100  # 需要3个批次

        with patch('ms_service_profiler.utils.trace_to_db.PROGRESS_REPORT_FREQUENCY', 2), \
                patch('ms_service_profiler.utils.trace_to_db.logger') as mock_logger:  # 每2个批次报告一次

            _write_data_batch(self.mock_cursor, "slice", data, batch_size,
                              "INSERT INTO slice VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")

        # 验证进度报告被调用
        progress_calls = [call for call in mock_logger.debug.call_args_list
                          if 'records' in str(call)]
        self.assertGreaterEqual(len(progress_calls), 1)


if __name__ == '__main__':
    unittest.main()