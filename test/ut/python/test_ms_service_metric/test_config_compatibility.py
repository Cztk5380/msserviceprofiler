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
import tempfile

from ms_service_metric.core.config.symbol_config import SymbolConfig


class TestConfigCompatibility:
    def test_array_format_config(self):
        config_content = """
- symbol: vllm.worker.model_runner:ModelRunner.execute_model
  handler: ms_service_metric.handlers:default_handler
  metrics:
    - name: vllm_model_execution_duration
      type: timer
      label:
        - name: model
          expr: self.model_config.model

- symbol: vllm.core.scheduler:Scheduler.schedule
  handler: ms_service_metric.handlers:default_handler
  metrics:
    - name: vllm_scheduler_duration
      type: timer
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            symbol_config = SymbolConfig(user_config_path=config_path)
            config = symbol_config.load()

            assert "vllm.worker.model_runner:ModelRunner.execute_model" in config
            assert "vllm.core.scheduler:Scheduler.schedule" in config

            first_symbol = config["vllm.worker.model_runner:ModelRunner.execute_model"]
            assert len(first_symbol) == 1
            assert first_symbol[0]["handler"] == "ms_service_metric.handlers:default_handler"
            assert "metrics" in first_symbol[0]
            assert first_symbol[0]["metrics"][0]["name"] == "vllm_model_execution_duration"
        finally:
            os.unlink(config_path)

    def test_dict_format_config(self):
        config_content = """
vllm.worker.model_runner:ModelRunner.execute_model:
  - handler: ms_service_metric.handlers:default_handler
    metrics:
      - name: vllm_model_execution_duration
        type: timer

vllm.core.scheduler:Scheduler.schedule:
  - handler: ms_service_metric.handlers:default_handler
    metrics:
      - name: vllm_scheduler_duration
        type: timer
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            symbol_config = SymbolConfig(user_config_path=config_path)
            config = symbol_config.load()

            assert "vllm.worker.model_runner:ModelRunner.execute_model" in config
            assert "vllm.core.scheduler:Scheduler.schedule" in config
        finally:
            os.unlink(config_path)

    def test_mixed_handlers_config(self):
        config_content = """
- symbol: test.module:function1
  handler: ms_service_metric.handlers:default_handler
  metrics:
    - name: func1_duration
      type: timer

- symbol: test.module:function2
  handler: ms_service_metric.handlers:default_handler
  metrics:
    - name: func2_calls
      type: counter

- symbol: test.module:function3
  handler: ms_service_metric.handlers:default_handler
  metrics:
    - name: func3_value
      type: gauge
      expr: len(args[0])
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            symbol_config = SymbolConfig(user_config_path=config_path)
            config = symbol_config.load()

            assert "test.module:function1" in config
            assert "test.module:function2" in config
            assert "test.module:function3" in config

            assert config["test.module:function1"][0]["handler"] == "ms_service_metric.handlers:default_handler"
            assert config["test.module:function2"][0]["handler"] == "ms_service_metric.handlers:default_handler"
            assert config["test.module:function3"][0]["handler"] == "ms_service_metric.handlers:default_handler"
        finally:
            os.unlink(config_path)

    def test_config_with_version_filters(self):
        config_content = """
- symbol: test.module:function
  handler: ms_service_metric.handlers:default_handler
  min_version: "0.5.0"
  max_version: "1.0.0"
  metrics:
    - name: func_duration
      type: timer
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            symbol_config = SymbolConfig(user_config_path=config_path)
            config = symbol_config.load()

            symbol_handlers = config["test.module:function"][0]
            assert symbol_handlers["min_version"] == "0.5.0"
            assert symbol_handlers["max_version"] == "1.0.0"
        finally:
            os.unlink(config_path)

    def test_empty_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            config_path = f.name

        try:
            symbol_config = SymbolConfig(user_config_path=config_path)
            config = symbol_config.get_config()
            assert config == {}
        finally:
            os.unlink(config_path)

    def test_config_with_labels(self):
        config_content = """
- symbol: test.module:function
  handler: ms_service_metric.handlers:default_handler
  metrics:
    - name: func_duration
      type: timer
      label:
        - name: status
          expr: ret['status']
        - name: model
          expr: args[0].model
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            symbol_config = SymbolConfig(user_config_path=config_path)
            config = symbol_config.load()

            metrics = config["test.module:function"][0]["metrics"]
            assert len(metrics[0]["label"]) == 2
            assert metrics[0]["label"][0]["name"] == "status"
            assert metrics[0]["label"][0]["expr"] == "ret['status']"
        finally:
            os.unlink(config_path)

