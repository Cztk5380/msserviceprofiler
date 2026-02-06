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

import sys
import types
from unittest.mock import Mock, patch, call, MagicMock
import pytest

from ms_service_profiler.patcher.sglang.handlers import scheduler_handlers

# 测试辅助类
class MockForwardMode:
    def __init__(self, is_decode=False, is_extend=False):
        self._is_decode = is_decode
        self._is_extend = is_extend
    
    def is_decode(self):
        return self._is_decode
    
    def is_extend(self):
        return self._is_extend

class MockReq:
    def __init__(self, rid, **kwargs):
        self.rid = rid
        self.is_retracted = kwargs.get('is_retracted', False)
        self._finished = kwargs.get('finished', False)
        self.is_chunked = kwargs.get('is_chunked', 0)
        self.output_ids = kwargs.get('output_ids', [])
        self.origin_input_ids = kwargs.get('origin_input_ids', [])
        self.is_generation = kwargs.get('is_generation', True)
        self.prefix_indices = kwargs.get('prefix_indices', [])
    
    def finished(self):
        return self._finished

class MockBatch:
    def __init__(self, reqs=None, forward_mode=None):
        self.reqs = reqs or []
        self.forward_mode = forward_mode

class TestSchedulerHandlers:
    """测试调度器处理器的主要功能"""
    
    def setup_method(self):
        """每个测试前的准备"""
        from ms_service_profiler import Profiler
        Profiler.reset()
    
    def test_batch_rid_extraction(self):
        """测试批处理ID提取"""
        reqs = [MockReq(rid=1), MockReq(rid=2)]
        batch = MockBatch(reqs=reqs)
        result = scheduler_handlers.prof_get_batch_rids(batch)
        assert result == ["1", "2"]
    
    @pytest.mark.parametrize("is_decode,is_extend,expected", [
        (True, False, "decode"),
        (False, True, "prefill"),
        (False, False, "unknown")
    ])
    def test_batch_type_detection(self, is_decode, is_extend, expected):
        """测试批处理类型检测"""
        mode = MockForwardMode(is_decode, is_extend)
        batch = MockBatch(forward_mode=mode)
        result = scheduler_handlers.get_batch_type(batch)
        assert result == expected
    
    def test_recv_requests_handler(self):
        """测试请求接收处理器"""
        mock_original = Mock()
        mock_req = Mock(spec=scheduler_handlers.TokenizedGenerateReqInput, rid=100)
        mock_original.return_value = [mock_req]
        
        result = scheduler_handlers.recv_requests(mock_original, Mock(), "arg")
        
        assert result == [mock_req]
        assert len(scheduler_handlers.Profiler.instance_calls) > 0
    
    def test_request_dispatcher(self):
        """测试请求分发器"""
        mock_original = Mock(return_value="result")
        mock_req = Mock(rid=200)
        
        result = scheduler_handlers.request_dispatcher(mock_original, Mock(), mock_req)
        
        assert result == "result"
        prof_calls = scheduler_handlers.Profiler.instance_calls[-1]
        assert any("span_start" in str(call) for call in prof_calls)
        assert any("span_end" in str(call) for call in prof_calls)
    
    def test_get_next_batch_with_batch(self):
        """测试获取批处理（有批处理的情况）"""
        mock_original = Mock()
        mock_req = MockReq(rid=300)
        mock_batch = MockBatch(reqs=[mock_req], forward_mode=MockForwardMode(is_decode=True))
        mock_original.return_value = mock_batch
        
        mock_scheduler = Mock()
        mock_scheduler.is_hybrid = False
        mock_scheduler._get_token_info.return_value = (1, 2, 3, 4)
        
        result = scheduler_handlers.get_next_batch_to_run(mock_original, mock_scheduler)
        
        assert result == mock_batch
        assert mock_original.called
    
    def test_get_next_batch_without_batch(self):
        """测试获取批处理（无批处理的情况）"""
        mock_original = Mock(return_value=None)
        result = scheduler_handlers.get_next_batch_to_run(mock_original, Mock())
        assert result is None
    
    def test_run_batch_execution(self):
        """测试批处理执行"""
        mock_original = Mock(return_value="exec_result")
        mock_req = MockReq(rid=400)
        mock_batch = MockBatch(reqs=[mock_req], forward_mode=MockForwardMode(is_extend=True))
        
        result = scheduler_handlers.run_batch(mock_original, Mock(), mock_batch)
        
        assert result == "exec_result"
        prof_calls = scheduler_handlers.Profiler.instance_calls[-1]
        assert any("modelExec" in str(call) for call in prof_calls)
    
    def test_queue_operations(self):
        """测试队列操作"""
        mock_original = Mock(return_value="queued")
        mock_req = Mock(rid=500)
        
        mock_scheduler = Mock()
        mock_scheduler.disaggregation_mode = scheduler_handlers.DisaggregationMode.NULL
        mock_scheduler._abort_on_queued_limit.return_value = False
        mock_scheduler.waiting_queue = [1, 2, 3]
        
        result = scheduler_handlers.add_request_to_queue(mock_original, mock_scheduler, mock_req, False)
        
        assert result == "queued"
        assert len(scheduler_handlers.Profiler.instance_calls) > 0
    
    def test_prefill_result_processing(self):
        """测试预填充结果处理"""
        mock_original = Mock(return_value="prefill_done")
        mock_req = MockReq(
            rid=600,
            finished=True,
            is_retracted=False,
            origin_input_ids=[1, 2, 3],
            output_ids=[4, 5]
        )
        mock_batch = MockBatch(reqs=[mock_req])
        
        mock_scheduler = Mock()
        mock_scheduler.is_generation = True
        mock_scheduler.enable_overlap = False
        mock_scheduler.is_hybrid = False
        mock_scheduler._get_token_info.return_value = (1, 2, 3, 4)
        
        result = scheduler_handlers.process_batch_result_prefill(
            mock_original, mock_scheduler, mock_batch
        )
        
        assert result == "prefill_done"
        prof_calls = scheduler_handlers.Profiler.instance_calls[0]
        assert any("PrefillEnd" in str(call) for call in prof_calls)
    
    def test_decode_result_processing(self):
        """测试解码结果处理"""
        mock_original = Mock(return_value="decode_done")
        mock_req = MockReq(
            rid=700,
            finished=True,
            is_retracted=False,
            origin_input_ids=[1, 2],
            output_ids=[3, 4, 5]
        )
        mock_batch = MockBatch(reqs=[mock_req])
        
        mock_scheduler = Mock()
        mock_scheduler.enable_overlap = False
        mock_scheduler.is_hybrid = False
        mock_scheduler._get_token_info.return_value = (1, 2, 3, 4)
        
        result = scheduler_handlers.process_batch_result_decode(
            mock_original, mock_scheduler, mock_batch
        )
        
        assert result == "decode_done"
        prof_calls = scheduler_handlers.Profiler.instance_calls[0]
        assert any("DecodeEnd" in str(call) for call in prof_calls)
    
    def test_cache_hit_rate_calculation(self):
        """测试缓存命中率计算"""
        mock_original = Mock(return_value="next_round")
        mock_req = Mock()
        mock_req.origin_input_ids = [1, 2, 3, 4, 5]
        mock_req.prefix_indices = [0, 1, 2]
        mock_req.rid = 800
        
        result = scheduler_handlers.init_next_round_input(mock_original, mock_req)
        
        assert result == "next_round"
        prof_calls = scheduler_handlers.Profiler.instance_calls[-1]
        assert any("hitRate" in str(call) for call in prof_calls)
    
    def test_batch_prefill_extraction(self):
        """测试批处理预填充提取"""
        mock_original = Mock()
        mock_req = MockReq(rid=900)
        mock_batch = MockBatch(reqs=[mock_req])
        mock_original.return_value = mock_batch
        
        mock_scheduler = Mock()
        mock_scheduler.waiting_queue = [1, 2]
        
        result = scheduler_handlers.get_new_batch_prefill(mock_original, mock_scheduler)
        
        assert result == mock_batch
        prof_calls = scheduler_handlers.Profiler.instance_calls[-1]
        assert any("Dequeue" in str(call) for call in prof_calls)

class TestKVCMetrics:
    """测试KV缓存指标"""
    
    def test_kvcache_hybrid_mode(self):
        """测试混合模式下的KV缓存指标"""
        mock_scheduler = Mock()
        mock_scheduler.is_hybrid = True
        mock_scheduler._get_swa_token_info.return_value = (1, 2, 3, 4, 5, 6, 7, 8)
        
        scheduler_handlers.prof_kvcache_info(mock_scheduler, "test")
        
        prof_calls = scheduler_handlers.Profiler.instance_calls[-1]
        assert any("fullEvictableSize" in str(call) for call in prof_calls)
        assert any("swaAvailableSize" in str(call) for call in prof_calls)
    
    def test_kvcache_standard_mode(self):
        """测试标准模式下的KV缓存指标"""
        mock_scheduler = Mock()
        mock_scheduler.is_hybrid = False
        mock_scheduler._get_token_info.return_value = (1, 2, 3, 4)
        
        scheduler_handlers.prof_kvcache_info(mock_scheduler, "test")
        
        prof_calls = scheduler_handlers.Profiler.instance_calls[-1]
        assert any("deviceBlock" in str(call) for call in prof_calls)

def test_complete_import_structure():
    """测试导入结构完整性"""
    assert hasattr(scheduler_handlers, 'Profiler')
    assert hasattr(scheduler_handlers, 'patcher')
    assert hasattr(scheduler_handlers, 'TokenizedGenerateReqInput')
    assert hasattr(scheduler_handlers, 'DisaggregationMode')