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
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import shutil
import yaml
import pytest
import requests
from msguard import GlobalConfig
import ms_serviceparam_optimizer
from ms_serviceparam_optimizer.config.config import get_settings, OptimizerConfigField, KubectlConfig, \
        MindieConfig
from ms_serviceparam_optimizer.config.custom_command import MindieCommand
from ms_serviceparam_optimizer.optimizer.simulator import enable_simulate_old
from ms_serviceparam_optimizer.optimizer.plugins.simulate import Simulator, DisaggregationSimulator



class TestSimulate(unittest.TestCase):

    def test_set_config_dict(self):
        origin_config = {"a": {"b": {"c": 3}}}
        Simulator.set_config(origin_config, "a.b.c", 4)
        assert origin_config["a"]["b"]["c"] == 4

    def test_set_config_list(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        Simulator.set_config(origin_config, "a.b.0.c", 4)
        assert origin_config["a"]["b"][0]["c"] == 4

    def test_set_config_new_key(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        Simulator.set_config(origin_config, "a.b.0.d", 4)
        assert origin_config["a"]["b"][0]["d"] == 4

    def test_set_config_add_dict_list_dict(self):
        origin_config = {"a": {"b": {"c": 3}}}
        Simulator.set_config(origin_config, "a.d.0.c", 4)
        assert origin_config["a"]["d"][0]["c"] == 4

    def test_set_config_add_dict(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        Simulator.set_config(origin_config, "a.b.1.c", 4)
        assert origin_config["a"]["b"][1]["c"] == 4

    def test_set_config_add_dict_list_dict_dict(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        Simulator.set_config(origin_config, "a.d.0.c.e", 4)
        assert origin_config["a"]["d"][0]["c"]["e"] == 4
    
    def test_is_int(self):
        # 测试is_int静态方法
        self.assertTrue(Simulator.is_int(1))
        self.assertTrue(Simulator.is_int("1"))
        self.assertFalse(Simulator.is_int("a"))


def test_enable_simulate_with_simulator(tmpdir, monkeypatch):
    config_path = Path(tmpdir).joinpath("config.json")
    with open(config_path, 'w') as f:
        f.write("""{
    "Version": "1.0.0",
    "ServerConfig": {
        "tlsCaFile": [
            "ca.pem"
        ],
        "tlsCert": "security/certs/server.pem"
    },
    "BackendConfig": {
        "backendName": "mindieservice_llm_engine",
        "ModelDeployConfig": {
            "maxSeqLen": 2560,
            "maxInputTokenLen": 2048,
            "truncation": false,
            "ModelConfig": [
                {
                    "modelInstanceType": "Standard"
                }
            ]
        },
        "ScheduleConfig": {
            "templateType": "Standard"
        }
    }
}""")
    get_settings().mindie.config_path = config_path
    get_settings().mindie.config_bak_path = Path(tmpdir).joinpath("config_bak.json")
    monkeypatch.setattr(MindieCommand, 'command', property(lambda self: ["echo"]))
    simulator = Simulator(get_settings().mindie)
    monkeypatch.setattr(ms_serviceparam_optimizer.optimizer.simulator, "simulate_flag", True)
    with enable_simulate_old(simulator) as flag:
        with open(config_path, 'r') as f:
            data = json.load(f)
            assert data["BackendConfig"]["ModelDeployConfig"]["ModelConfig"][0][
                       "plugin_params"] == '{"plugin_type": "simulate"}'
    with open(config_path, 'r') as f:
        data = json.load(f)
        assert "plugin_params" not in data["BackendConfig"]["ModelDeployConfig"]["ModelConfig"][0]


def test_enable_simulate_with_simulator_plugin_params_exists(tmpdir, monkeypatch):
    config_path = Path(tmpdir).joinpath("config.json")
    data = {
        "BackendConfig": {
            "backendName": "mindieservice_llm_engine",
            "ModelDeployConfig": {
                "maxSeqLen": 2560,
                "ModelConfig": [
                    {
                        "modelInstanceType": "Standard",
                        "plugin_params": "{\"plugin_type\":\"tp\"}"
                    }
                ]

            },
            "ScheduleConfig": {
                "templateType": "Standard"
            }
        }
    }
    with open(config_path, 'w') as f:
        json.dump(data, f)
    get_settings().mindie.config_path = config_path
    get_settings().mindie.config_bak_path = Path(tmpdir).joinpath("config_bak.json")
    monkeypatch.setattr(MindieCommand, 'command', property(lambda self: ["echo"]))
    simulator = Simulator(get_settings().mindie)
    monkeypatch.setattr(ms_serviceparam_optimizer.optimizer.simulator, "simulate_flag", True)
    with enable_simulate_old(simulator) as flag:
        with open(config_path, 'r') as f:
            data = json.load(f)
            assert data["BackendConfig"]["ModelDeployConfig"]["ModelConfig"][0][
                       "plugin_params"] == '{"plugin_type": "tp,simulate"}'
    with open(config_path, 'r') as f:
        data = json.load(f)
        assert data["BackendConfig"]["ModelDeployConfig"]["ModelConfig"][0]["plugin_params"] == '{"plugin_type":"tp"}'


class TestVllmSimulator(unittest.TestCase):
    """测试 VllmSimulator 类"""

    def setUp(self):
        # 创建模拟的 VllmConfig
        self.mock_config = MagicMock()
        self.mock_config.process_name = "vllm"
        self.mock_config.command = MagicMock()
        self.mock_config.command.host = "localhost"
        self.mock_config.command.port = "8000"
        self.mock_config.command.model = "gpt2"
        self.mock_config.command.served_model_name = "gpt2"
        self.mock_config.command.others = ""

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    def test_init(self, mock_which):
        """测试 VllmSimulator 初始化"""
        mock_which.return_value = "/usr/local/bin/vllm"
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        self.assertEqual(simulator.config, self.mock_config)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    def test_base_url_property(self, mock_which):
        """测试 base_url 属性"""
        mock_which.return_value = "/usr/local/bin/vllm"
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        expected_url = "http://localhost:8000/health"
        self.assertEqual(simulator.base_url, expected_url)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.CustomProcess.stop')
    def test_stop(self, mock_super_stop, mock_run, mock_which):
        """测试 stop 方法"""
        mock_which.return_value = "/usr/local/bin/vllm"
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        # mock _is_vllm_running 返回 False，表示没有进程需要停止
        with patch.object(simulator, '_is_vllm_running', return_value=False):
            simulator.stop()
        mock_super_stop.assert_called_once()

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    def test_stop_vllm_process_success(self, mock_run, mock_which):
        """测试 _stop_vllm_process 成功停止进程"""
        mock_which.return_value = "/usr/local/bin/vllm"
        mock_run.return_value = MagicMock(returncode=0)
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        
        # 模拟进程检查 - 第一次运行，进程存在；之后不存在
        with patch.object(simulator, '_is_vllm_running', side_effect=[True, False]):
            result = simulator._stop_vllm_process(max_attempts=1, timeout=1)
            self.assertTrue(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    def test_stop_vllm_process_already_stopped(self, mock_run, mock_which):
        """测试 _stop_vllm_process 进程已经停止"""
        mock_which.return_value = "/usr/local/bin/vllm"
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        
        # 模拟进程已经不存在
        with patch.object(simulator, '_is_vllm_running', return_value=False):
            result = simulator._stop_vllm_process(max_attempts=1, timeout=1)
            self.assertTrue(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    def test_stop_vllm_process_no_pkill(self, mock_which):
        """测试 _stop_vllm_process 找不到 pkill 命令"""
        mock_which.return_value = "/usr/local/bin/vllm"
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        # 模拟进程存在但找不到 pkill
        with patch.object(simulator, '_is_vllm_running', return_value=True):
            # 需要额外 mock simulate 模块中的 shutil.which
            with patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.shutil.which', return_value=None):
                result = simulator._stop_vllm_process()
                self.assertFalse(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    def test_is_vllm_running_true(self, mock_run, mock_simulate_which, mock_config_which):
        """测试 _is_vllm_running 返回 True"""
        mock_config_which.return_value = "/usr/local/bin/vllm"
        mock_simulate_which.return_value = "/usr/bin/pgrep"  # _is_vllm_running 使用的是 simulate 模块的 shutil.which
        mock_run.return_value = MagicMock(stdout="5\n", returncode=0)
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        result = simulator._is_vllm_running()
        self.assertTrue(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    def test_is_vllm_running_false(self, mock_run, mock_simulate_which, mock_config_which):
        """测试 _is_vllm_running 返回 False"""
        mock_config_which.return_value = "/usr/local/bin/vllm"
        mock_simulate_which.return_value = "/usr/bin/pgrep"
        mock_run.return_value = MagicMock(stdout="0\n", returncode=0)
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        result = simulator._is_vllm_running()
        self.assertFalse(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    def test_is_vllm_running_exception(self, mock_run, mock_simulate_which, mock_config_which):
        """测试 _is_vllm_running 异常处理"""
        mock_config_which.return_value = "/usr/local/bin/vllm"
        mock_simulate_which.return_value = "/usr/bin/pgrep"
        mock_run.side_effect = subprocess.SubprocessError("Command failed")
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        result = simulator._is_vllm_running()
        self.assertFalse(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.time.time')
    def test_wait_for_process_exit_success(self, mock_time, mock_which):
        """测试 _wait_for_process_exit 成功退出"""
        mock_which.return_value = "/usr/local/bin/vllm"
        mock_time.side_effect = [0, 0.3, 0.6]  # 模拟时间流逝
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        
        with patch.object(simulator, '_is_vllm_running', side_effect=[True, False]):
            result = simulator._wait_for_process_exit(timeout=1)
            self.assertTrue(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.time.time')
    def test_wait_for_process_exit_timeout(self, mock_time, mock_which):
        """测试 _wait_for_process_exit 超时"""
        mock_which.return_value = "/usr/local/bin/vllm"
        mock_time.side_effect = [0, 1, 2, 3]  # 模拟超时
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        
        with patch.object(simulator, '_is_vllm_running', return_value=True):
            result = simulator._wait_for_process_exit(timeout=1)
            self.assertFalse(result)

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    def test_log_residual_processes(self, mock_run, mock_which):
        """测试 _log_residual_processes 方法"""
        mock_which.return_value = "/usr/local/bin/vllm"
        mock_run.return_value = MagicMock(stdout="1234 /usr/bin/vllm\n5678 /usr/bin/vllm\n")
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        simulator._log_residual_processes()
        mock_run.assert_called_once()

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.subprocess.run')
    def test_log_residual_processes_exception(self, mock_run, mock_which):
        """测试 _log_residual_processes 异常处理"""
        mock_which.return_value = "/usr/local/bin/vllm"
        mock_run.side_effect = subprocess.SubprocessError("Command failed")
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        simulator._log_residual_processes()  # 不应抛出异常

    @patch('ms_serviceparam_optimizer.config.custom_command.shutil.which')
    def test_update_command(self, mock_which):
        """测试 update_command 方法"""
        mock_which.return_value = "/usr/local/bin/vllm"
        from ms_serviceparam_optimizer.optimizer.plugins.simulate import VllmSimulator
        simulator = VllmSimulator(self.mock_config)
        original_command = simulator.command
        simulator.update_command()
        self.assertIsNotNone(simulator.command)


class TestDisaggregationSimulator(unittest.TestCase):
    def setUp(self):
        # 创建临时测试环境
        self.test_dir = Path("conf")
        self.yaml_dir = Path("deployment")
        self.test_dir.mkdir(exist_ok=True)
        self.yaml_dir.mkdir(exist_ok=True)
        self.config_single_path = self.test_dir / "config.json"
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b"MindIE-MS coordinator is ready!!!")
        self.temp_file.close()
        data = {
            "BackendConfig": {
                "backendName": "mindieservice_llm_engine",
                "ModelDeployConfig": {
                    "maxSeqLen": 2560,
                    "ModelConfig": [
                        {
                            "modelInstanceType": "Standard",
                            "plugin_params": "{\"plugin_type\":\"tp\"}"
                        }
                    ]

                },
                "ScheduleConfig": {
                    "templateType": "Standard"
                }
            }
        }
        with open(self.config_single_path, 'w') as f:
            json.dump(data, f)
        pd_data = {
            "default_p_rate": 1,
            "default_d_rate": 3
        }
        self.kubectl_single_path = self.test_dir / "deploy.sh"
        self.config_single_pd_path = self.test_dir / "ms_controller.json"
        self.yaml_path = self.yaml_dir / "mindie_service_single_container.yaml"
        service_config = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "mindie-service",
                "labels": {
                    "app": "mindie-server"
                }
            },
            "spec": {
                "selector": {
                    "app": "mindie-server"
                },
                "ports": [
                    {
                        "name": "http",
                        "port": 1025,
                        "targetPort": 1025,
                        "nodePort": 31015,
                        "protocol": "TCP"
                    }
                ],
                "type": "NodePort",
                "sessionAffinity": "None"
            }
        }
        with open(self.yaml_path, 'w') as file:
            yaml.dump(service_config, file, default_flow_style=False)
        with open(self.config_single_pd_path, 'w') as fout:
            json.dump(pd_data, fout)
        self.config_single_bak_path = self.test_dir / "config_bak.json"
        self.config_single_pd_bak_path = self.test_dir / "ms_bak_controller.json"


    def tearDown(self):
        # 清理临时目录
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.yaml_dir)
        os.unlink(self.temp_file.name)

    def test_set_config_dict(self):
        origin_config = {"a": {"b": {"c": 3}}}
        DisaggregationSimulator.set_config(origin_config, "a.b.c", 4)
        assert origin_config["a"]["b"]["c"] == 4

    def test_set_config_list(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        DisaggregationSimulator.set_config(origin_config, "a.b.0.c", 4)
        assert origin_config["a"]["b"][0]["c"] == 4

    def test_set_config_new_key(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        DisaggregationSimulator.set_config(origin_config, "a.b.0.d", 4)
        assert origin_config["a"]["b"][0]["d"] == 4

    def test_set_config_add_dict_list_dict(self):
        origin_config = {"a": {"b": {"c": 3}}}
        DisaggregationSimulator.set_config(origin_config, "a.d.0.c", 4)
        assert origin_config["a"]["d"][0]["c"] == 4

    def test_set_config_add_dict(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        DisaggregationSimulator.set_config(origin_config, "a.b.1.c", 4)
        assert origin_config["a"]["b"][1]["c"] == 4

    def test_set_config_add_dict_list_dict_dict(self):
        origin_config = {"a": {"b": [{"c": 3}]}}
        DisaggregationSimulator.set_config(origin_config, "a.d.0.c.e", 4)
        assert origin_config["a"]["d"][0]["c"]["e"] == 4

    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.logger')
    def test_is_int(self, mock_logger):
        # 测试is_int方法
        self.assertTrue(DisaggregationSimulator.is_int('123'))
        self.assertFalse(DisaggregationSimulator.is_int('abc'))

    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.logger')
    def test_stop(self, mock_logger):
        # 测试stop方法
        mindie_config = KubectlConfig()
        simulator = DisaggregationSimulator(mindie_config)
        simulator.stop()
        # 验证日志记录是否正确
        mock_logger.debug.assert_called()

    @patch('requests.post') 
    def test_curl_success(self, mock_post):
        # Arrange
        mindie_config = KubectlConfig()
        mindie_config.config_single_path = self.config_single_path
        mindie_config.kubectl_single_path = self.kubectl_single_path
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        test_class = DisaggregationSimulator(mindie_config) 

        # Act
        result = test_class.test_curl()

        # Assert
        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('requests.post') 
    def test_curl_failure(self, mock_post):
        # Arrange
        mindie_config = KubectlConfig()
        mindie_config.kubectl_single_path = self.kubectl_single_path
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        test_class = DisaggregationSimulator(mindie_config)  

        # Act
        result = test_class.test_curl()

        # Assert
        self.assertFalse(result)
        mock_post.assert_called_once()

    @patch('requests.post')  
    def test_curl_exception(self, mock_post):
        # Arrange
        mindie_config = KubectlConfig()
        mindie_config.kubectl_single_path = self.kubectl_single_path
        mock_post.side_effect = requests.exceptions.RequestException
        test_class = DisaggregationSimulator(mindie_config)  

        # Act
        result = test_class.test_curl()

        # Assert
        self.assertFalse(result)
        mock_post.assert_called_once()

    def test_update_config(self):
        # Arrange
        mindie_config = KubectlConfig()
        mindie_config.config_single_path = self.config_single_path
        mindie_config.config_single_pd_path = self.config_single_pd_path
        simulator = DisaggregationSimulator(mindie_config)
        
        # 创建测试参数
        params = [
            OptimizerConfigField(config_position="BackendConfig.ModelDeployConfig.maxSeqLen", value=4096),
            OptimizerConfigField(config_position="default_p_rate", value=2)
        ]
        
        # Act
        simulator.update_config(params)
        
        # Assert
        with open(self.config_single_path, 'r') as f:
            config_data = json.load(f)
            self.assertEqual(config_data["BackendConfig"]["ModelDeployConfig"]["maxSeqLen"], 4096)
        
        with open(self.config_single_pd_path, 'r') as f:
            pd_config_data = json.load(f)
            self.assertEqual(pd_config_data["default_p_rate"], 2)

    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.DisaggregationSimulator.test_curl')
    @patch('msguard.security.io.open_s')
    def test_health(self, mock_open, mock_test_curl):
        # Arrange
        GlobalConfig.custom_return = True
        mindie_config = KubectlConfig()
        simulator = DisaggregationSimulator(mindie_config)
        simulator.run_log = self.temp_file.name
        simulator.mindie_log_offset = 0
        
        # 模拟文件读取返回包含成功信息的内容
        mock_file = Mock()
        mock_file.read.return_value = "MindIE-MS coordinator is ready!!!"
        mock_file.tell.return_value = 100
        mock_open.return_value.__enter__.return_value = mock_file
        
        # 模拟test_curl返回True
        mock_test_curl.return_value = True
        
        # Act
        result = simulator.health()
        
        # Assert
        self.assertTrue(result)
        mock_test_curl.assert_called_once()
        GlobalConfig.reset()
    
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.DisaggregationSimulator.update_config')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.DisaggregationSimulator.start_server')
    @patch('ms_serviceparam_optimizer.optimizer.plugins.simulate.logger')
    def test_run(self, mock_logger, mock_start_server, mock_update_config):
        # Arrange
        mindie_config = KubectlConfig()
        simulator = DisaggregationSimulator(mindie_config)
        
        # 创建测试参数
        params = [OptimizerConfigField(config_position="BackendConfig.ModelDeployConfig.maxSeqLen", value=4096)]
        
        # Act
        simulator.run(params)
        
        # Assert
        mock_logger.info.assert_called_once()
        mock_update_config.assert_called_once_with(params)
        mock_start_server.assert_called_once_with(params)