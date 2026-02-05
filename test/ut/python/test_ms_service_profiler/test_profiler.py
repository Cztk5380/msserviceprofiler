# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of the Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import unittest
from unittest.mock import patch, MagicMock
import json
from ms_service_profiler.profiler import (
    Profiler,
    MarkType,
    Level,
    initialize_profiler,
    prof_step
)


class TestMarkType(unittest.TestCase):

    def test_mark_type_values(self):
        """测试MarkType枚举值"""
        self.assertEqual(MarkType.TYPE_EVENT.value, 0)
        self.assertEqual(MarkType.TYPE_METRIC.value, 1)
        self.assertEqual(MarkType.TYPE_SPAN.value, 2)
        self.assertEqual(MarkType.TYPE_LINK.value, 3)


class TestLevel(unittest.TestCase):

    def test_level_values(self):
        """测试Level枚举值"""
        self.assertEqual(Level.ERROR.value, 10)
        self.assertEqual(Level.INFO.value, 20)
        self.assertEqual(Level.DETAILED.value, 30)
        self.assertEqual(Level.VERBOSE.value, 40)
        self.assertEqual(Level.LEVEL_CORE_TRACE.value, 10)
        self.assertEqual(Level.LEVEL_NORMAL_TRACE.value, 20)
        self.assertEqual(Level.LEVEL_DETAILED_TRACE.value, 30)
        self.assertEqual(Level.L0.value, 10)
        self.assertEqual(Level.L1.value, 20)
        self.assertEqual(Level.L2.value, 30)


class TestProfiler(unittest.TestCase):

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_init_enabled(self, mock_is_enable):
        """测试Profiler初始化（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        self.assertTrue(profiler.enable)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_init_disabled(self, mock_is_enable):
        """测试Profiler初始化（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        self.assertFalse(profiler.enable)

    def test_profiler_context_manager(self):
        """测试Profiler上下文管理器"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            self.assertTrue(profiler.enable)

            result = profiler.__enter__()
            self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_exit_with_span_end(self, mock_is_enable):
        """测试Profiler退出时调用span_end"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._span_handle = MagicMock()

        with patch.object(profiler, 'span_end') as mock_span_end:
            profiler.__exit__(None, None, None)
            mock_span_end.assert_called_once()

    def test_profiler_attr(self):
        """测试attr方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.attr('key1', 'value1')
            self.assertEqual(profiler._attr['key1'], 'value1')
            self.assertEqual(result, profiler)

    def test_profiler_attr_multiple(self):
        """测试多个attr调用"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            profiler.attr('key1', 'value1').attr('key2', 'value2')
            self.assertEqual(profiler._attr['key1'], 'value1')
            self.assertEqual(profiler._attr['key2'], 'value2')

    @patch('ms_service_profiler.profiler.service_profiler.is_domain_enable')
    def test_profiler_domain(self, mock_is_domain_enable):
        """测试domain方法"""
        mock_is_domain_enable.return_value = True
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.domain('TestDomain')
            self.assertEqual(profiler._domain, 'TestDomain')
            self.assertTrue(profiler._enable)
            self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_domain_enable')
    def test_profiler_domain_disabled(self, mock_is_domain_enable):
        """测试domain方法（域禁用）"""
        mock_is_domain_enable.return_value = False
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            profiler.domain('TestDomain')
            self.assertFalse(profiler._enable)

    def test_profiler_res(self):
        """测试res方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.res('request_id_123')
            self.assertEqual(profiler._attr['rid'], 'request_id_123')
            self.assertEqual(result, profiler)

    def test_profiler_metric(self):
        """测试metric方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric('response_time', 100)
            self.assertEqual(profiler._attr['response_time='], 100)
            self.assertEqual(result, profiler)

    def test_profiler_metric_inc(self):
        """测试metric_inc方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric_inc('counter', 1)
            self.assertEqual(profiler._attr['counter+'], 1)
            self.assertEqual(result, profiler)

    def test_profiler_metric_scope(self):
        """测试metric_scope方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric_scope('request_count', 5)
            self.assertEqual(profiler._attr['scope#request_count'], 5)
            self.assertEqual(result, profiler)

    def test_profiler_metric_scope_as_req_id(self):
        """测试metric_scope_as_req_id方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric_scope_as_req_id()
            self.assertEqual(profiler._attr['scope#'], 'req')
            self.assertEqual(result, profiler)

    def test_profiler_get_attrs_json_empty(self):
        """测试_get_attrs_json方法（空属性）"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler._get_attrs_json()
            self.assertEqual(result, "")

    def test_profiler_get_attrs_json_with_data(self):
        """测试_get_attrs_json方法（有数据）"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            profiler._attr = {'key1': 'value1', 'key2': 'value2'}
            result = profiler._get_attrs_json()
            expected = json.dumps({'key1': 'value1', 'key2': 'value2'})
            self.assertEqual(result, expected)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_launch_disabled(self, mock_is_enable):
        """测试launch方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.launch()
        self.assertIsNone(profiler._name)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_launch_enabled(self, mock_mark, mock_is_enable):
        """测试launch方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.launch()
        self.assertEqual(profiler._name, "Launch")
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_EVENT)
        mock_mark.assert_called_once()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_link_disabled(self, mock_is_enable):
        """测试link方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.link('from_rid', 'to_rid')
        self.assertIsNone(profiler._name)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_link_enabled(self, mock_mark, mock_is_enable):
        """测试link方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.link('from_rid', 'to_rid')
        self.assertEqual(profiler._name, "Link")
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_LINK)
        self.assertEqual(profiler._attr["from"], "from_rid")
        self.assertEqual(profiler._attr["to"], "to_rid")
        mock_mark.assert_called_once()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_event_disabled(self, mock_is_enable):
        """测试event方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.event('test_event')
        self.assertIsNone(profiler._name)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_event_enabled(self, mock_mark, mock_is_enable):
        """测试event方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.event('test_event')
        self.assertEqual(profiler._name, 'test_event')
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_EVENT)
        mock_mark.assert_called_once()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_span_start_disabled(self, mock_is_enable):
        """测试span_start方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        result = profiler.span_start('test_span')
        self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.start_span')
    def test_profiler_span_start_enabled(self, mock_start_span, mock_is_enable):
        """测试span_start方法（启用状态）"""
        mock_is_enable.return_value = True
        mock_start_span.return_value = 'span_handle_123'
        profiler = Profiler(Level.L0)
        result = profiler.span_start('test_span')
        self.assertEqual(profiler._name, 'test_span')
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_SPAN)
        self.assertEqual(profiler._span_handle, 'span_handle_123')
        self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_span_end_disabled(self, mock_is_enable):
        """测试span_end方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.span_end()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_span_end_no_handle(self, mock_is_enable):
        """测试span_end方法（无span handle）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._span_handle = None
        profiler.span_end()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.span_end_ex')
    def test_profiler_span_end_with_handle(self, mock_span_end, mock_is_enable):
        """测试span_end方法（有span handle）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._name = 'test_span'
        profiler._domain = 'TestDomain'
        profiler._attr = {'key': 'value'}
        profiler._span_handle = 'handle_123'

        with patch.object(profiler, '_get_attrs_json', return_value='{"key": "value"}'):
            profiler.span_end()
            mock_span_end.assert_called_once_with(
                'test_span', 'TestDomain', '{"key": "value"}', 'handle_123'
            )

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_mark_event_ex_disabled(self, mock_is_enable):
        """测试_mark_event_ex方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler._name = 'test_event'
        profiler._domain = 'TestDomain'
        profiler._mark_event_ex()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_mark_event_ex_enabled(self, mock_mark, mock_is_enable):
        """测试_mark_event_ex方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._name = 'test_event'
        profiler._domain = 'TestDomain'
        profiler._attr = {'key': 'value'}

        with patch.object(profiler, '_get_attrs_json', return_value='{"key": "value"}'):
            profiler._mark_event_ex()
            mock_mark.assert_called_once_with('test_event', 'TestDomain', '{"key": "value"}')

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_add_meta_info_disabled(self, mock_is_enable):
        """测试add_meta_info方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.add_meta_info('meta_key', 'meta_data')

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.add_meta_info')
    def test_profiler_add_meta_info_enabled(self, mock_add_meta, mock_is_enable):
        """测试add_meta_info方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.add_meta_info('meta_key', 'meta_data')
        mock_add_meta.assert_called_once_with('meta_key', 'meta_data')


class TestInitializeProfiler(unittest.TestCase):

    @patch.dict('ms_service_profiler.profiler.__dict__', {'torch': MagicMock()})
    @patch('ms_service_profiler.profiler.torch_prof_total_steps', 0)
    @patch('ms_service_profiler.profiler.service_profiler.get_acl_task_time_level')
    @patch('ms_service_profiler.profiler.service_profiler.get_acl_prof_aicore_metrics')
    @patch('ms_service_profiler.profiler.service_profiler.get_prof_path')
    @patch('ms_service_profiler.profiler.service_profiler.is_torch_prof_stack')
    @patch('ms_service_profiler.profiler.service_profiler.is_torch_prof_modules')
    @patch('ms_service_profiler.profiler.service_profiler.get_torch_prof_step_num')
    @patch('ms_service_profiler.profiler.logger')
    def test_initialize_profiler_no_steps(
        self, mock_logger, mock_get_steps, mock_is_stack, mock_is_modules,
        mock_get_path, mock_get_aicore, mock_get_task_level
    ):
        """测试initialize_profiler（无步骤限制）"""
        mock_get_task_level.return_value = 'L1'
        mock_get_aicore.return_value = 1
        mock_get_path.return_value = '/tmp/prof'
        mock_is_stack.return_value = False
        mock_is_modules.return_value = False
        mock_get_steps.return_value = 0

        import sys
        from unittest.mock import MagicMock

        mock_torch = MagicMock()
        mock_torch_npu = MagicMock()
        mock_torch.npu = mock_torch_npu
        type(mock_torch_npu).profiler = MagicMock()

        sys.modules['torch'] = mock_torch
        sys.modules['torch_npu'] = mock_torch_npu

        try:
            from ms_service_profiler import profiler as profiler_module
            profiler_module.torch_prof = None
            profiler_module.torch_prof_total_steps = 0
            profiler_module.initialize_profiler()
        finally:
            if 'torch' in sys.modules:
                del sys.modules['torch']
            if 'torch_npu' in sys.modules:
                del sys.modules['torch_npu']

if __name__ == '__main__':
    unittest.main()
