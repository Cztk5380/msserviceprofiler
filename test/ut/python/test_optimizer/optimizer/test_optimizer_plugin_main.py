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
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ms_serviceparam_optimizer.config import config as config_module
from ms_serviceparam_optimizer.config.base_config import EnginePolicy
from ms_serviceparam_optimizer.config.config import BenchMarkPolicy, DeployPolicy, OptimizerConfigField
from ms_serviceparam_optimizer.optimizer.optimizer import plugin_main


def _build_plugin_args(config):
    args = MagicMock()
    args.benchmark_policy = BenchMarkPolicy.vllm_benchmark.value
    args.deploy_policy = DeployPolicy.single.value
    args.backup = False
    args.load_breakpoint = False
    args.engine = EnginePolicy.vllm.value
    args.config = config
    return args


def test_plugin_main_with_missing_custom_config_returns(tmp_path):
    missing_config = tmp_path / "missing.toml"
    args = _build_plugin_args(str(missing_config))

    with patch("ms_serviceparam_optimizer.optimizer.register.register_ori_functions"):
        with patch(
            "ms_serviceparam_optimizer.optimizer.optimizer.Rule.input_file_read.is_satisfied_by", return_value=False
        ):
            with patch("ms_serviceparam_optimizer.optimizer.optimizer.logger.error") as mock_error:
                plugin_main(args)

    mock_error.assert_called_once_with("Custom config file not found: {}", missing_config.resolve())


def test_plugin_main_with_invalid_custom_config_raises(tmp_path):
    custom_config = tmp_path / "invalid.toml"
    custom_config.write_text("invalid = [", encoding="utf-8")
    args = _build_plugin_args(str(custom_config))

    with patch("ms_serviceparam_optimizer.optimizer.register.register_ori_functions"):
        with patch(
            "ms_serviceparam_optimizer.optimizer.optimizer.Rule.input_file_read.is_satisfied_by", return_value=True
        ):
            with pytest.raises(ValueError, match="Invalid TOML config file"):
                plugin_main(args)


def test_plugin_main_with_custom_config_registers_settings(tmp_path):
    custom_config = tmp_path / "custom.toml"
    custom_config.write_text("n_particles = 1\n", encoding="utf-8")
    args = _build_plugin_args(str(custom_config))
    target_field = (
        OptimizerConfigField(
            name="max_batch_size",
            config_position="BackendConfig.ScheduleConfig.maxBatchSize",
            min=10,
            max=100,
            dtype="int",
        ),
    )
    settings = MagicMock()
    default_toml_file = Path("/default/config.toml")

    class DummySettings:
        model_config = {"toml_file": [default_toml_file], "env_prefix": "model_eval_state_"}

    class FakeSimulator:
        data_field = target_field

        def __init__(self, *args, **kwargs):
            pass

    class FakeBenchmark:
        data_field = ()

        def __init__(self, *args, **kwargs):
            pass

    with ExitStack() as stack:
        stack.enter_context(patch.object(config_module, "Settings", DummySettings))
        mock_register_settings = stack.enter_context(patch.object(config_module, "register_settings"))
        stack.enter_context(patch.object(config_module, "get_settings", return_value=settings))
        stack.enter_context(
            patch(
                "ms_serviceparam_optimizer.optimizer.optimizer.Rule.input_file_read.is_satisfied_by",
                return_value=True,
            )
        )
        stack.enter_context(patch("ms_serviceparam_optimizer.optimizer.register.register_ori_functions"))
        stack.enter_context(patch("ms_serviceparam_optimizer.optimizer.optimizer.simulates", {"vllm": FakeSimulator}))
        stack.enter_context(
            patch("ms_serviceparam_optimizer.optimizer.optimizer.benchmarks", {"vllm_benchmark": FakeBenchmark})
        )
        stack.enter_context(patch("ms_serviceparam_optimizer.optimizer.store.DataStorage"))
        stack.enter_context(patch("ms_serviceparam_optimizer.optimizer.scheduler.Scheduler"))
        stack.enter_context(patch("ms_serviceparam_optimizer.optimizer.experience_fine_tunning.FineTune"))
        pso = stack.enter_context(patch("ms_serviceparam_optimizer.optimizer.optimizer.PSOOptimizer"))

        plugin_main(args)

    mock_register_settings.assert_called_once()
    custom_settings = mock_register_settings.call_args.args[0]()
    assert custom_settings.model_config["toml_file"] == [default_toml_file, custom_config.resolve()]
    assert custom_settings.model_config["extra"] == "allow"
    pso.return_value.run_plugin.assert_called_once()
