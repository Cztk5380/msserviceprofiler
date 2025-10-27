# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import MagicMock, patch
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

    # 函数
    convert_ts_to_ns,
    trans_trace_meta_data,
    trans_trace_slice_data,
    trans_trace_flow_data,
    trans_trace_counter_data,

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
    save_cache_data_to_db
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


if __name__ == '__main__':
    unittest.main()