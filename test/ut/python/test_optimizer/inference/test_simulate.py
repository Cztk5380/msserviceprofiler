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
import os
import signal
import tempfile
import threading
import time
import queue
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import pytest
import numpy as np
import torch

from modelevalstate.config.config import get_settings
from modelevalstate.inference.simulate import (
    Simulate, predict_queue, ServiceField, FileLogger, write_file, 
    signal_handler, sub_thread
)
from modelevalstate.inference.data_format_v1 import BatchField, RequestField


class TestWriteFileFunction:
    """测试write_file函数的各种边界情况和错误处理"""
    
    def test_write_file_normal_operation(self):
        """测试write_file函数的正常操作"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            
            # 添加一些测试数据到队列
            test_data = ["test1", "test2", "test3"]
            for data in test_data:
                predict_queue.put(data)
            predict_queue.put(None)  # 结束信号
            
            # 启动write_file函数
            write_thread = threading.Thread(target=write_file, args=(file_logger,))
            write_thread.start()
            write_thread.join(timeout=5)
            
            # 验证文件内容
            with open(file_path, 'r') as f:
                content = f.read()
                for data in test_data:
                    assert data in content
    
    def test_write_file_empty_queue(self):
        """测试空队列情况"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            
            # 直接放入结束信号
            predict_queue.put(None)
            
            # 启动write_file函数
            write_thread = threading.Thread(target=write_file, args=(file_logger,))
            write_thread.start()
            write_thread.join(timeout=5)
            
            # 验证文件为空
            with open(file_path, 'r') as f:
                content = f.read()
                assert content == ""
    
    def test_write_file_with_exception_in_write(self):
        """测试写入时发生异常的情况"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            
            # 模拟写入时发生异常
            with patch.object(file_logger, 'write', side_effect=Exception("Write error")):
                predict_queue.put("test_data")
                predict_queue.put(None)
                
                # 启动write_file函数，应该能正常结束
                write_thread = threading.Thread(target=write_file, args=(file_logger,))
                write_thread.start()
                write_thread.join(timeout=5)
                
                # 验证线程正常结束
                assert not write_thread.is_alive()
    
    def test_write_file_large_data_volume(self):
        """测试大数据量写入"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            
            # 添加大量数据到队列
            large_data = [f"data_{i}" for i in range(1000)]
            for data in large_data:
                predict_queue.put(data)
            predict_queue.put(None)
            
            # 启动write_file函数
            write_thread = threading.Thread(target=write_file, args=(file_logger,))
            write_thread.start()
            write_thread.join(timeout=10)
            
            # 验证所有数据都被写入
            with open(file_path, 'r') as f:
                content = f.read()
                for data in large_data:
                    assert data in content
    
    def test_write_file_concurrent_access(self):
        """测试并发访问情况"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            
            def producer():
                """生产者线程，不断添加数据"""
                for i in range(100):
                    predict_queue.put(f"concurrent_data_{i}")
                    time.sleep(0.01)
                predict_queue.put(None)
            
            # 启动生产者和消费者
            producer_thread = threading.Thread(target=producer)
            consumer_thread = threading.Thread(target=write_file, args=(file_logger,))
            
            producer_thread.start()
            consumer_thread.start()
            
            producer_thread.join(timeout=5)
            consumer_thread.join(timeout=5)
            
            # 验证数据完整性
            with open(file_path, 'r') as f:
                content = f.read()
                for i in range(100):
                    assert f"concurrent_data_{i}" in content


class TestSignalHandler:
    """测试信号处理函数的各种情况"""
    
    def test_signal_handler_normal_operation(self):
        """测试信号处理函数的正常操作"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            file_logger.open_file()
            
            # 模拟子线程
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            
            with patch('modelevalstate.inference.simulate.sub_thread', mock_thread):
                signal_handler(file_logger)
            
            # 验证队列中放入None
            assert predict_queue.get() is None
            # 验证文件被关闭
            assert file_logger.fout is None
    
    def test_signal_handler_thread_timeout(self):
        """测试子线程超时情况"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            file_logger.open_file()
            
            # 模拟一直存活的子线程
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = True
            
            with patch('modelevalstate.inference.simulate.sub_thread', mock_thread):
                with pytest.raises(TimeoutError, match="子线程未在指定时间完成"):
                    signal_handler(file_logger)
    
    def test_signal_handler_no_sub_thread(self):
        """测试没有子线程的情况"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_output.log"
            file_logger = FileLogger(file_path)
            file_logger.open_file()
            
            with patch('modelevalstate.inference.simulate.sub_thread', None):
                signal_handler(file_logger)
            
            # 验证队列中放入None
            assert predict_queue.get() is None
            # 验证文件被关闭
            assert file_logger.fout is None


class TestFileLoggerEdgeCases:
    """测试FileLogger类的边界情况"""
    
    def test_file_logger_repeated_open_close(self):
        """测试重复打开关闭文件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.log"
            logger = FileLogger(file_path)
            
            # 多次打开关闭
            for i in range(5):
                logger.open_file()
                logger.write(f"test_{i}")
                logger.close()
            
            # 验证文件内容
            with open(file_path, 'r') as f:
                content = f.read()
                for i in range(5):
                    assert f"test_{i}" in content
    
    def test_file_logger_concurrent_writes(self):
        """测试并发写入"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.log"
            logger = FileLogger(file_path)
            logger.open_file()
            
            def write_data(thread_id, count):
                for i in range(count):
                    logger.write(f"thread_{thread_id}_data_{i}")
            
            # 启动多个写入线程
            threads = []
            for i in range(5):
                thread = threading.Thread(target=write_data, args=(i, 10))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join(timeout=5)
            
            logger.close()
            
            # 验证所有数据都被写入
            with open(file_path, 'r') as f:
                content = f.read()
                for i in range(5):
                    for j in range(10):
                        assert f"thread_{i}_data_{j}" in content
    
    def test_file_logger_special_characters(self):
        """测试特殊字符写入"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.log"
            logger = FileLogger(file_path)
            logger.open_file()
            
            special_messages = [
                "普通消息",
                "消息 with spaces",
                "消息 with\t tabs",
                "消息 with\n newlines",
                "消息 with 中文",
                "消息 with 🚀 emoji",
                "消息 with \"quotes\"",
                "消息 with 'apostrophes'",
                "消息 with \\backslashes\\",
            ]
            
            for message in special_messages:
                logger.write(message)
            
            logger.close()
            
            # 验证文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for message in special_messages:
                    assert message in content


class TestSimulateEdgeCases:
    """测试Simulate类的边界情况和错误处理"""
    
    def test_generate_random_token_invalid_shape(self):
        """测试无效形状的token生成"""
        plugin_object = MagicMock()
        plugin_object.eos_token_id = 10000
        
        # 测试形状乘积超过最大值
        with pytest.raises(ValueError, match="token数量超过词表的范围"):
            Simulate.generate_random_token(plugin_object, (1000, 1000), max_value=10000)
    
    def test_generate_random_token_zero_shape(self):
        """测试零形状的token生成"""
        plugin_object = MagicMock()
        plugin_object.eos_token_id = 10000
        
        # 测试零形状
        result = Simulate.generate_random_token(plugin_object, (0,), max_value=10000)
        assert result.shape == (0,)
        assert result.size == 0
    
    def test_generate_logits_large_vocab_size(self):
        """测试大词汇量的logits生成"""
        # 测试边界值
        for vocab_size in [129280, 1000000]:
            logits = Simulate.generate_logits(1, vocab_size, device="cpu")
            assert logits.shape == (1, vocab_size)
            assert logits.dtype == torch.float16


class TestIntegrationScenarios:
    """测试集成场景"""
    def test_prediction_cache_behavior(self):
        """测试预测缓存行为"""
        # 清空缓存
        Simulate.predict_cache = {}
        
        # 设置测试数据
        ServiceField.batch_field = BatchField("decode", 10, 100.0, 500.0, 50.0)
        ServiceField.request_field = (RequestField(50.0, 5, 10),) * 10
        
        # 模拟预测函数
        with patch('modelevalstate.inference.simulate.predict_v1_with_cache') as mock_predict:
            mock_predict.return_value = (-1, 200000)
            
            # 第一次调用，应该调用预测函数
            result1 = Simulate.predict()
            assert mock_predict.call_count == 1
            assert len(Simulate.predict_cache) == 1
            
            # 第二次调用，应该使用缓存
            result2 = Simulate.predict()
            assert mock_predict.call_count == 1  # 调用次数不变
            assert result1 == result2


@pytest.mark.parametrize("batch_size,vocab_size", [
    (1, 128), (10, 1024), (100, 129280), (1000, 10000)
])
def test_generate_logits_parameterized(batch_size, vocab_size):
    """参数化测试generate_logits函数"""
    logits = Simulate.generate_logits(batch_size, vocab_size, device="cpu")
    assert logits.shape == (batch_size, vocab_size)
    assert logits.dtype == torch.float16


@pytest.mark.slow
def test_performance_large_scale():
    """性能测试：大规模数据生成"""
    start_time = time.time()
    
    # 生成大量logits
    for i in range(100):
        Simulate.generate_logits(100, 1000, device="cpu")
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    # 验证执行时间在合理范围内
    assert execution_time < 10.0  # 10秒内完成