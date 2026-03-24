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
import unittest
from copy import deepcopy
import numpy as np
from ms_serviceparam_optimizer.config.config import (
    map_param_with_value, OptimizerConfigField,
    ErrorPatternConfig, HealthCheckConfig,
    ErrorType, ErrorSeverity
)


class TestMapParamWithValueRealFields(unittest.TestCase):
    def setUp(self):

        self.default_support_field = [
            OptimizerConfigField(name="max_batch_size", 
                               config_position="BackendConfig.ScheduleConfig.maxBatchSize", 
                               min=25, max=300, dtype="int"),
            OptimizerConfigField(name="max_prefill_batch_size",
                               config_position="BackendConfig.ScheduleConfig.maxPrefillBatchSize", 
                               min=1, max=25, dtype="int"),
            OptimizerConfigField(name="prefill_time_ms_per_req",
                               config_position="BackendConfig.ScheduleConfig.prefillTimeMsPerReq", 
                               max=1000, dtype="int"),
            OptimizerConfigField(name="decode_time_ms_per_req",
                               config_position="BackendConfig.ScheduleConfig.decodeTimeMsPerReq", 
                               max=1000, dtype="int"),
            OptimizerConfigField(name="support_select_batch",
                               config_position="BackendConfig.ScheduleConfig.supportSelectBatch", 
                               max=1, dtype="bool"),
            OptimizerConfigField(name="max_prefill_token",
                               config_position="BackendConfig.ScheduleConfig.maxPrefillTokens", 
                               min=4096, max=409600, dtype="int"),
            OptimizerConfigField(name="max_queue_deloy_microseconds",
                               config_position="BackendConfig.ScheduleConfig.maxQueueDelayMicroseconds", 
                               min=500, max=1000000, dtype="int"),
            OptimizerConfigField(name="prefill_policy_type",
                               config_position="BackendConfig.ScheduleConfig.prefillPolicyType", 
                               min=0, max=1, dtype="enum", dtype_param=[0, 1, 3]),
            OptimizerConfigField(name="decode_policy_type",
                               config_position="BackendConfig.ScheduleConfig.decodePolicyType", 
                               min=0, max=1, dtype="enum", dtype_param=[0, 1, 3]),
            OptimizerConfigField(name="max_preempt_count",
                               config_position="BackendConfig.ScheduleConfig.maxPreemptCount", 
                               min=0, max=1, dtype="ratio", dtype_param="max_batch_size")
        ]
        self.pd_field = [
            OptimizerConfigField(name="default_p_rate", 
                               config_position="default_p_rate", 
                               min=1, max=3, dtype="int", value=1),
            OptimizerConfigField(name="default_d_rate", 
                               config_position="default_d_rate", 
                               min=1, max=3, dtype="share", dtype_param="default_p_rate"),
        ]

    def test_int_type_with_min_max(self):
        # 测试 int 类型（带 min/max 约束）
        params = np.array([26.7, 12.3, 999.9, 500.0, 0.6, 40960.0, 750000.0])
        result = map_param_with_value(params, self.default_support_field[:7])
        
        # 验证字段值是否符合预期
        self.assertEqual(result[0].value, 26) 
        self.assertEqual(result[1].value, 12)  
        self.assertEqual(result[2].value, 999)  
        self.assertEqual(result[3].value, 500)   
        self.assertTrue(result[4].value)  
        self.assertEqual(result[5].value, 40960) 
        self.assertEqual(result[6].value, 750000) 

    def test_enum_type_mapping(self):
        # 测试 enum 类型的分段映射
        params = np.array([0.0, 0.3, 0.6, 1.0])
        enum_fields = [
            self.default_support_field[7],  # prefill_policy_type (enum [0,1,3])
            self.default_support_field[8]   # decode_policy_type (enum [0,1,3])
        ]
        result = map_param_with_value(params, enum_fields)
        
        # 验证 enum 分段逻辑
        self.assertEqual(result[0].value, 0) 
        self.assertEqual(result[1].value, 0)


    def test_ratio_type_dependency(self):
        # 测试 ratio 类型（依赖 max_batch_size）
        params = np.array([0.5])
        ratio_field = self.default_support_field[9]  # max_preempt_count (ratio)
        
        # 手动设置依赖字段的值
        max_batch_size_field = OptimizerConfigField(
            name="max_batch_size", config_position="BackendConfig.ScheduleConfig.maxBatchSize", dtype="int", value=100,   
        )
        
        result = map_param_with_value(params, [max_batch_size_field])
        self.assertEqual(result[0].value, 0)  
    
    def test_share_type_mapping(self):
        params = np.array([1, 2])
        share_ratio = map_param_with_value(params, self.pd_field)
        self.assertEqual(share_ratio[1].value, 3)

    def test_edge_cases(self):
        # 测试边界条件
        params = np.array([24.9, 0.0, 0.0, 0.0, 0.4, 4095.9, 499.9, -1.0, 2.0, 1.1])
        result = map_param_with_value(params, self.default_support_field)
        
        # 验证边界处理
        self.assertEqual(result[0].value, 24)
        self.assertEqual(result[1].value, 1)
        self.assertFalse(result[4].value)
        self.assertEqual(result[5].value, 4095)
        self.assertEqual(result[6].value, 499)
        self.assertEqual(result[7].value, 0)


class TestErrorPatternConfig(unittest.TestCase):
    """测试 ErrorPatternConfig 配置类"""

    def test_custom_patterns(self):
        """测试自定义错误模式"""
        custom_config = ErrorPatternConfig(
            fatal_patterns={
                ErrorType.OUT_OF_MEMORY: ["custom OOM pattern"]
            },
            retryable_patterns={
                ErrorType.NETWORK_ERROR: ["custom network pattern"]
            }
        )
        self.assertEqual(len(custom_config.fatal_patterns[ErrorType.OUT_OF_MEMORY]), 1)
        self.assertEqual(custom_config.fatal_patterns[ErrorType.OUT_OF_MEMORY][0], "custom OOM pattern")
        self.assertEqual(custom_config.retryable_patterns[ErrorType.NETWORK_ERROR][0], "custom network pattern")

    def test_empty_patterns(self):
        """测试空错误模式"""
        empty_config = ErrorPatternConfig(
            fatal_patterns={},
            retryable_patterns={}
        )
        self.assertEqual(len(empty_config.fatal_patterns), 0)
        self.assertEqual(len(empty_config.retryable_patterns), 0)


class TestHealthCheckConfig(unittest.TestCase):
    """测试 HealthCheckConfig 配置类"""

    def test_default_service_errors(self):
        """测试默认的 service_errors 配置"""
        config = HealthCheckConfig()
        self.assertIsInstance(config.service_errors, ErrorPatternConfig)
        self.assertIn(ErrorType.OUT_OF_MEMORY, config.service_errors.fatal_patterns)
        self.assertIn(ErrorType.NETWORK_ERROR, config.service_errors.retryable_patterns)

    def test_default_benchmark_errors(self):
        """测试默认的 benchmark_errors 配置"""
        config = HealthCheckConfig()
        self.assertIsInstance(config.benchmark_errors, ErrorPatternConfig)
        self.assertEqual(len(config.benchmark_errors.fatal_patterns), 0)
        self.assertIn(ErrorType.NETWORK_ERROR, config.benchmark_errors.retryable_patterns)
        self.assertIn(ErrorType.IO_ERROR, config.benchmark_errors.retryable_patterns)

    def test_custom_log_snippet_length(self):
        """测试自定义 log_snippet_length"""
        config = HealthCheckConfig(log_snippet_length=500)
        self.assertEqual(config.log_snippet_length, 500)

    def test_custom_health_check_config(self):
        """测试自定义健康检查配置"""
        custom_config = HealthCheckConfig(
            service_errors=ErrorPatternConfig(
                fatal_patterns={ErrorType.DEVICE_ERROR: ["device fault"]},
                retryable_patterns={}
            ),
            benchmark_errors=ErrorPatternConfig(
                fatal_patterns={},
                retryable_patterns={ErrorType.IO_ERROR: ["disk full"]}
            ),
            log_snippet_length=300
        )
        self.assertIn("device fault", custom_config.service_errors.fatal_patterns[ErrorType.DEVICE_ERROR])
        self.assertIn("disk full", custom_config.benchmark_errors.retryable_patterns[ErrorType.IO_ERROR])
        self.assertEqual(custom_config.log_snippet_length, 300)
