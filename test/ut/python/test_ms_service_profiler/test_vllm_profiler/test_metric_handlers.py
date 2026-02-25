# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import time
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from typing import Any, Dict, List

from ms_service_profiler.patcher.core.metric_hook import HookMetrics, MetricType, MetricConfig
from ms_service_profiler.patcher.vllm.handlers.v1.metric_handlers import (
    Timeline,
    TimingContextManager,
    record_function_timer_hook,
    record_function_timer_hook_vllm_ascend,
    runner_get_output_hooker,
    scheduler_scheduler_hooker,
    _get_or_create_metric,
    size_buckets,
    timeline_recored,
    metrics_client,
)


@pytest.fixture
def mock_state():
    """模拟状态对象"""
    with patch('ms_service_profiler.patcher.vllm.handlers.v1.metric_handlers._get_state') as mock_get_state:
        state = Mock()
        state.dp_rank_id = 0
        mock_get_state.return_value = state
        yield state


@pytest.fixture
def mock_hook_metrics():
    """模拟 HookMetrics 客户端"""
    with patch('ms_service_profiler.patcher.vllm.handlers.v1.metric_handlers.get_hook_metrics') as mock_get_metrics:
        mock_client = Mock(spec=HookMetrics)
        mock_client.metrics = {}
        mock_client.register_metric = Mock()
        mock_client.record_metric = Mock()
        mock_get_metrics.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_time():
    """模拟时间函数"""
    with patch('time.time') as mock_time_func:
        mock_time_func.side_effect = [100.0, 100.5, 101.0, 101.3, 102.0, 102.4]  # 多组时间值
        yield mock_time_func


@pytest.fixture(autouse=True)
def reset_timeline():
    """每个测试前重置 timeline 状态"""
    timeline_recored.time_recorded.clear()
    yield


@pytest.fixture
def mock_metrics_client():
    """模拟全局 metrics_client"""
    with patch('ms_service_profiler.patcher.vllm.handlers.v1.metric_handlers.metrics_client') as mock_client:
        mock_client.record_metric = Mock()
        yield mock_client


class TestGetOrCreateMetric:
    """测试 _get_or_create_metric 函数"""

    def test_given_metric_not_exists_when_get_or_create_then_create_new_metric(self, mock_hook_metrics):
        """给定指标不存在时，获取或创建指标应创建新指标"""
        # Given
        metric_name = "test_timer"
        label_names = ["name"]
        metric_type = MetricType.TIMER
        buckets = [1, 10, 100]

        # When
        result = _get_or_create_metric(metric_name, label_names, metric_type, buckets)

        # Then
        assert result == mock_hook_metrics
        mock_hook_metrics.register_metric.assert_called_once()
        call_args = mock_hook_metrics.register_metric.call_args[0]
        assert call_args[0].name == metric_name
        assert call_args[0].type == metric_type
        assert call_args[0].buckets == buckets

    def test_given_metric_exists_when_get_or_create_then_return_existing_metric(self, mock_hook_metrics):
        """给定指标已存在时，获取或创建指标应返回现有指标"""
        # Given
        metric_name = "existing_timer"
        mock_hook_metrics.metrics[metric_name] = Mock()

        # When
        result = _get_or_create_metric(metric_name)

        # Then
        assert result == mock_hook_metrics
        mock_hook_metrics.register_metric.assert_not_called()


class TestTimeline:
    """测试 Timeline 类"""

    @pytest.fixture
    def timeline(self, mock_hook_metrics):
        """创建 Timeline 实例"""
        return Timeline()

    def test_given_valid_forward_duration_when_record_then_record_duration(self, timeline, mock_hook_metrics):
        """给定有效的 forward_duration 记录时，应正确记录持续时间"""
        # Given
        start_name = "forward"
        trigger_name = "model_runner_get_output"
        metric_name = "npu:forward_duration"
        
        # When
        timeline.record(start_name, 100.0, 10.0)  # 记录起始点
        timeline.record(trigger_name, 110.0, 5.0)  # 记录触发点

        # Then
        mock_hook_metrics.record_metric.assert_called_once()
        call_args = mock_hook_metrics.record_metric.call_args[0]
        assert call_args[0] == metric_name
        assert call_args[1] == 15.0  # end_time - start_time = 115 - 100
        assert call_args[2] == {}

    def test_given_valid_kernel_launch_when_record_then_record_duration(self, timeline, mock_hook_metrics):
        """给定有效的 kernel_launch 记录时，应正确记录持续时间"""
        # Given
        start_name = "forward"
        trigger_name = "post process"
        metric_name = "npu:kernel_launch"
        
        # When
        timeline.record(start_name, 200.0, 20.0)  # 记录起始点
        timeline.record(trigger_name, 220.0, 3.0)  # 记录触发点

        # Then
        mock_hook_metrics.record_metric.assert_called_once()
        call_args = mock_hook_metrics.record_metric.call_args[0]
        assert call_args[0] == metric_name
        assert call_args[1] == 23.0  # end_time - start_time = 223 - 200
        assert call_args[2] == {}

    def test_given_trigger_without_start_when_record_then_skip_recording(self, timeline, mock_hook_metrics):
        """给定触发点记录但无起始点时，应跳过记录"""
        # Given
        trigger_name = "model_runner_get_output"
        
        # When
        timeline.record(trigger_name, 110.0, 5.0)

        # Then
        mock_hook_metrics.record_metric.assert_not_called()
        # 验证没有记录任何时间点（因为不在 time_record_set 中）
        assert trigger_name not in timeline.time_recorded

    def test_given_start_name_in_time_record_set_when_record_then_store_time(self, timeline, mock_hook_metrics):
        """给定起始点在 time_record_set 中时，应存储时间点"""
        # Given
        start_name = "forward"
        
        # When
        timeline.record(start_name, 100.0, 10.0)

        # Then
        assert start_name in timeline.time_recorded
        assert timeline.time_recorded[start_name] == (100.0, 110.0)
        mock_hook_metrics.record_metric.assert_not_called()

    def test_given_name_not_in_time_record_set_when_record_then_do_nothing(self, timeline, mock_hook_metrics):
        """给定名称不在 time_record_set 中时，不应做任何记录"""
        # Given
        unknown_name = "unknown_event"
        
        # When
        timeline.record(unknown_name, 100.0, 10.0)

        # Then
        assert unknown_name not in timeline.time_recorded
        mock_hook_metrics.record_metric.assert_not_called()


class TestTimingContextManager:
    """测试 TimingContextManager 类"""

    @pytest.fixture
    def original_context(self):
        """创建原始上下文管理器"""
        context = Mock()
        context.__enter__ = Mock(return_value="context_value")
        context.__exit__ = Mock(return_value=None)
        return context

    def test_given_no_exception_when_enter_exit_then_record_duration(self, mock_time, mock_hook_metrics, original_context, mock_metrics_client):
        """给定无异常发生时，进入和退出上下文应记录持续时间"""
        # Given
        label_name = "test_operation"
        manager = TimingContextManager(label_name, original_context)

        # When
        with manager as value:
            pass

        # Then
        assert value == "context_value"
        original_context.__enter__.assert_called_once()
        original_context.__exit__.assert_called_once()
        
        mock_metrics_client.record_metric.assert_called_once()
        call_args = mock_metrics_client.record_metric.call_args[0]
        assert call_args[0] == "record_function_or_nullcontext"
        assert call_args[1] == 0.5  # 100.5 - 100.0
        assert call_args[2] == {"name": label_name}

    def test_given_exception_when_enter_exit_then_skip_recording(self, mock_time, mock_metrics_client, original_context):
        """给定异常发生时，退出上下文应跳过记录"""
        # Given
        label_name = "test_operation"
        manager = TimingContextManager(label_name, original_context)

        # When/Then
        with pytest.raises(ValueError):
            with manager:
                raise ValueError("Test exception")

        # Then
        mock_metrics_client.record_metric.assert_not_called()
        original_context.__exit__.assert_called_once()

    def test_given_original_context_without_methods_when_enter_exit_then_handle_gracefully(self, mock_time, mock_metrics_client):
        """给定原始上下文管理器没有 __enter__/__exit__ 方法时，应优雅处理"""
        # Given
        label_name = "test_operation"
        original_context = object()  # 没有 __enter__/__exit__ 方法的对象
        
        # When/Then
        with pytest.raises(AttributeError):
            # 由于原始对象没有 __enter__ 方法，应该抛出 AttributeError
            manager = TimingContextManager(label_name, original_context)
            with manager:
                pass


class TestRecordFunctionTimerHook:
    """测试 record_function_timer_hook 函数"""

    def test_given_valid_name_when_hook_called_then_return_timing_manager(self):
        """给定有效的名称时，hook 应返回计时上下文管理器"""
        # Given
        original_context = Mock()
        original_func = Mock(return_value=original_context)
        name = "test_operation"
        args = ["arg1", "arg2"]
        kwargs = {"key": "value"}

        # When
        result = record_function_timer_hook(original_func, name, *args, **kwargs)

        # Then
        assert isinstance(result, TimingContextManager)
        assert result.label_name == name
        assert result.original_context == original_context
        original_func.assert_called_once_with(name, *args, **kwargs)


class TestRecordFunctionTimerHookVLLMAscend:
    """测试 record_function_timer_hook_vllm_ascend 函数"""

    def test_given_valid_name_when_hook_called_then_return_timing_manager(self):
        """给定有效的名称时，vllm_ascend hook 应返回计时上下文管理器"""
        # Given
        original_context = Mock()
        original_func = Mock(return_value=original_context)
        self_obj = Mock()
        name = "test_operation"
        args = ["arg1", "arg2"]
        kwargs = {"key": "value"}

        # When
        result = record_function_timer_hook_vllm_ascend(original_func, self_obj, name, *args, **kwargs)

        # Then
        assert isinstance(result, TimingContextManager)
        assert result.label_name == name
        assert result.original_context == original_context
        original_func.assert_called_once_with(self_obj, name, *args, **kwargs)


class TestRunnerGetOutputHooker:
    """测试 runner_get_output_hooker 函数"""

    def test_given_valid_call_when_hook_called_then_record_duration(self, mock_time, mock_metrics_client):
        """给定有效调用时，hook 应记录执行时间"""
        # Given
        original_func = Mock(return_value="result")
        args = [1, 2, 3]
        kwargs = {"key": "value"}

        # When
        result = runner_get_output_hooker(original_func, *args, **kwargs)

        # Then
        assert result == "result"
        original_func.assert_called_once_with(*args, **kwargs)
        
        mock_metrics_client.record_metric.assert_called_once()
        call_args = mock_metrics_client.record_metric.call_args[0]
        assert call_args[0] == "worker:model_runner_get_output:duration"
        assert call_args[1] == 0.5
        assert call_args[2] == {}


class TestSchedulerSchedulerHooker:
    """测试 scheduler_scheduler_hooker 函数"""

    @pytest.fixture
    def mock_scheduler(self):
        """模拟调度器对象"""
        scheduler = Mock()
        scheduler.running = ["req1", "req2", "req3"]  # 3 个运行中的请求
        return scheduler

    @pytest.fixture
    def mock_ret(self):
        """模拟返回值对象"""
        ret = Mock()
        ret.num_scheduled_tokens = [10, 20, 30]  # 3 个批次
        
        # 模拟 scheduled_new_reqs
        new_req1 = Mock(num_computed_tokens=50)
        new_req2 = Mock(num_computed_tokens=60)
        ret.scheduled_new_reqs = [new_req1, new_req2]
        
        # 模拟 scheduled_cached_reqs
        cached_reqs = Mock()
        cached_reqs.num_computed_tokens = [70, 80]
        ret.scheduled_cached_reqs = cached_reqs
        
        ret.total_num_scheduled_tokens = 100
        return ret

    def test_given_valid_scheduler_when_hook_called_then_record_all_metrics(
        self, mock_time, mock_metrics_client, mock_scheduler, mock_ret
    ):
        """给定有效的调度器调用时，hook 应记录所有指标"""
        # Given
        original_func = Mock(return_value=mock_ret)
        args = ["arg1", "arg2"]
        kwargs = {"key": "value"}

        # When
        result = scheduler_scheduler_hooker(original_func, mock_scheduler, *args, **kwargs)

        # Then
        assert result == mock_ret
        original_func.assert_called_once_with(mock_scheduler, *args, **kwargs)
        
        # 验证记录调用了多次
        assert mock_metrics_client.record_metric.call_count >= 4
        
        # 获取所有调用
        calls = mock_metrics_client.record_metric.call_args_list
        
        # 验证具体的指标记录
        metric_calls = {call[0][0]: call[0][1] for call in calls}
        
        assert metric_calls["scheduler:duration"] == 0.5
        assert metric_calls["scheduler:batch_size"] == 3
        assert metric_calls["scheduler:running_queue_size"] == 3
        
        # 计算期望的 seqlen 平均值
        expected_avg = (50 + 60 + 70 + 80 + 100) / 4  # (new_reqs + cached_reqs) / cnt
        assert metric_calls["scheduler:seqlen:avg"] == expected_avg
        assert metric_calls["scheduler:seqlen:sum"] == 50 + 60 + 70 + 80 + 100

    def test_given_empty_scheduler_when_hook_called_then_skip_seqlen_metrics(
        self, mock_time, mock_metrics_client, mock_scheduler
    ):
        """给定空调度器时，hook 应跳过 seqlen 指标记录"""
        # Given
        ret = Mock()
        ret.num_scheduled_tokens = []
        ret.scheduled_new_reqs = []
        ret.scheduled_cached_reqs = Mock(num_computed_tokens=[])
        ret.total_num_scheduled_tokens = 0
        
        original_func = Mock(return_value=ret)

        # When
        result = scheduler_scheduler_hooker(original_func, mock_scheduler)

        # Then
        assert result == ret
        
        # 验证只记录了基本指标，没有 seqlen 指标
        assert mock_metrics_client.record_metric.call_count == 3  # duration, batch_size, running_queue_size
        
        calls = mock_metrics_client.record_metric.call_args_list
        metric_names = [call[0][0] for call in calls]
        assert "scheduler:seqlen:avg" not in metric_names
        assert "scheduler:seqlen:sum" not in metric_names

    def test_given_scheduler_with_only_new_reqs_when_hook_called_then_correct_seqlen(
        self, mock_time, mock_metrics_client, mock_scheduler
    ):
        """给定只有新请求的调度器时，应正确计算 seqlen"""
        # Given
        ret = Mock()
        ret.num_scheduled_tokens = [10]
        
        # 只有新请求
        new_req1 = Mock(num_computed_tokens=50)
        new_req2 = Mock(num_computed_tokens=60)
        ret.scheduled_new_reqs = [new_req1, new_req2]
        
        # 没有缓存请求
        cached_reqs = Mock()
        cached_reqs.num_computed_tokens = []
        ret.scheduled_cached_reqs = cached_reqs
        
        ret.total_num_scheduled_tokens = 100
        
        original_func = Mock(return_value=ret)

        # When
        result = scheduler_scheduler_hooker(original_func, mock_scheduler)

        # Then
        assert result == ret
        
        calls = mock_metrics_client.record_metric.call_args_list
        metric_values = {call[0][0]: call[0][1] for call in calls}
        
        expected_avg = (50 + 60 + 100) / 2  # 只有新请求的数量
        assert metric_values["scheduler:seqlen:avg"] == expected_avg
        assert metric_values["scheduler:seqlen:sum"] == 50 + 60 + 100

    def test_given_scheduler_with_only_cached_reqs_when_hook_called_then_correct_seqlen(
        self, mock_time, mock_metrics_client, mock_scheduler
    ):
        """给定只有缓存请求的调度器时，应正确计算 seqlen"""
        # Given
        ret = Mock()
        ret.num_scheduled_tokens = [10]
        
        # 没有新请求
        ret.scheduled_new_reqs = []
        
        # 只有缓存请求
        cached_reqs = Mock()
        cached_reqs.num_computed_tokens = [70, 80, 90]
        ret.scheduled_cached_reqs = cached_reqs
        
        ret.total_num_scheduled_tokens = 100
        
        original_func = Mock(return_value=ret)

        # When
        result = scheduler_scheduler_hooker(original_func, mock_scheduler)

        # Then
        assert result == ret
        
        calls = mock_metrics_client.record_metric.call_args_list
        metric_values = {call[0][0]: call[0][1] for call in calls}
        
        expected_avg = (70 + 80 + 90 + 100) / 3  # 只有缓存请求的数量
        assert metric_values["scheduler:seqlen:avg"] == expected_avg
        assert metric_values["scheduler:seqlen:sum"] == 70 + 80 + 90 + 100


class TestEdgeCases:
    """测试边界情况"""

    def test_size_buckets_contains_infinity(self):
        """测试 size_buckets 包含无穷大"""
        # Given/When/Then
        assert float('inf') in size_buckets
        assert size_buckets[-1] == float('inf')

    def test_size_buckets_contains_common_values(self):
        """测试 size_buckets 包含常用值"""
        # Given/When/Then
        assert 0 in size_buckets
        assert 100 in size_buckets
        assert 1000 in size_buckets
        assert 10000 in size_buckets
        assert 262144 in size_buckets

    def test_timeline_duration_config_structure(self):
        """测试 Timeline 的 duration_config 结构"""
        # Given/When
        timeline = Timeline()
        
        # Then
        assert "npu:forward_duration" in timeline.duration_config
        assert "npu:kernel_launch" in timeline.duration_config
        assert timeline.duration_config["npu:forward_duration"] == ("forward", "model_runner_get_output")
        assert timeline.duration_config["npu:kernel_launch"] == ("forward", "post process")
        
        # 验证 time_record_set
        assert "forward" in timeline.time_record_set
        assert len(timeline.time_record_set) == 1  # 只有一个起始点 "forward"
        
        # 验证 duration_activate_dict
        assert "model_runner_get_output" in timeline.duration_activate_dict
        assert "post process" in timeline.duration_activate_dict
        assert timeline.duration_activate_dict["model_runner_get_output"] == ("forward", "npu:forward_duration")
        assert timeline.duration_activate_dict["post process"] == ("forward", "npu:kernel_launch")


class TestNegativeCases:
    """测试反例"""

    def test_given_invalid_metric_type_when_register_then_raise_error(self, mock_hook_metrics):
        """给定无效的指标类型时，注册指标应抛出错误"""
        # Given
        metric_name = "invalid_metric"
        invalid_type = "INVALID_TYPE"
        
        # 模拟 register_metric 抛出异常
        mock_hook_metrics.register_metric.side_effect = ValueError("Invalid metric type")

        # When/Then
        with pytest.raises(ValueError) as exc_info:
            metric_config = MetricConfig(
                name=metric_name,
                type=invalid_type,
                expr=""
            )
            mock_hook_metrics.register_metric(metric_config, ["name"])
        
        assert "Invalid metric type" in str(exc_info.value)

    def test_given_negative_duration_when_record_then_handle_gracefully(self, mock_hook_metrics):
        """给定负的持续时间时，应优雅处理"""
        # Given
        timeline = Timeline()
        
        # When
        timeline.record("forward", 100.0, -10.0)  # 负的持续时间
        
        # Then - 不应该抛出异常，时间点被记录但结束时间可能小于开始时间
        assert "forward" in timeline.time_recorded
        assert timeline.time_recorded["forward"] == (100.0, 90.0)  # 允许负的持续时间导致结束时间小于开始时间

    def test_given_none_for_original_context_when_timing_context_manager_then_handle_gracefully(self):
        """给定 None 作为原始上下文管理器时，应优雅处理"""
        # Given
        label_name = "test"
        original_context = None
        
        # When/Then
        with pytest.raises(AttributeError):
            # None 对象没有 __enter__ 方法，应该抛出 AttributeError
            manager = TimingContextManager(label_name, original_context)
            with manager:
                pass

    def test_given_empty_name_when_record_function_timer_hook_then_handle_gracefully(self):
        """给定空字符串作为名称时，hook 应正常处理"""
        # Given
        original_context = Mock()
        original_func = Mock(return_value=original_context)
        name = ""
        
        # When
        result = record_function_timer_hook(original_func, name)
        
        # Then
        assert isinstance(result, TimingContextManager)
        assert result.label_name == ""
