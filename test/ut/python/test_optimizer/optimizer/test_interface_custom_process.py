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
import subprocess
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call

import psutil
import pytest

from ms_serviceparam_optimizer.config.config import (
    CUSTOM_OUTPUT,
    MODEL_EVAL_STATE_CONFIG_PATH,
    OptimizerConfigField, get_settings
)
from ms_serviceparam_optimizer.optimizer.interfaces.custom_process import CustomProcess, tempfile, os, BaseDataField


def test_before_run_no_run_params(monkeypatch):
    # 模拟 tempfile.mkstemp
    monkeypatch.setattr(tempfile, "mkstemp", lambda prefix="": (1234, 'tempfile'))
    # 模拟 os.environ
    monkeypatch.setattr(os, "environ", {})
    process = CustomProcess()
    process.before_run()

    # 验证属性设置
    assert process.run_log_fp == 1234
    assert process.run_log == 'tempfile'
    assert process.run_log_offset == 0


def test_before_run_with_run_params():
    process = CustomProcess()
    process.command = ["benchmark", "$CONCURRENCY", "$REQUESTRATE"]
    run_params = (
        OptimizerConfigField(name="CONCURRENCY", config_position="env", min=10, max=1000, dtype="int", value=10),
        OptimizerConfigField(name="REQUESTRATE", config_position="env", min=0.1, max=0.7, value=0.3, dtype="float"),
    )
    process.before_run(run_params)
    assert process.command == ["benchmark", "10", "0.3"]


def test_before_run_env_var_already_set(monkeypatch):
    # 模拟 os.environ
    monkeypatch.setattr(os, "environ", {CUSTOM_OUTPUT: "/result",
                                        MODEL_EVAL_STATE_CONFIG_PATH: "config.toml"})

    process = CustomProcess()
    process.before_run()

    # 验证 tempfile.mkstemp 被调用
    assert os.environ[CUSTOM_OUTPUT] == "/result"
    assert os.environ[MODEL_EVAL_STATE_CONFIG_PATH] == "config.toml"


def test_check_success_process_still_running(tmpdir):
    # 模拟子进程仍在运行
    custom_process = CustomProcess()
    custom_process.run_log = Path(tmpdir).joinpath("run_log")
    custom_process.run_log_offset = 0
    with open(custom_process.run_log, "w") as f:
        f.write("test")
    custom_process.process = Mock()
    custom_process.process.poll.return_value = None
    custom_process.print_log = True


def test_check_success_process_succeeded(tmpdir):
    # 模拟子进程成功完成
    custom_process = CustomProcess()
    custom_process.run_log = Path(tmpdir).joinpath("run_log")
    custom_process.run_log_offset = 0
    with open(custom_process.run_log, "w") as f:
        f.write("test")
    custom_process.process = Mock()
    custom_process.process.poll.return_value = 0
    custom_process.print_log = True


@patch("psutil.process_iter")
@patch("ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_process")
def test_check_env_no_residual_process(mock_kill_process, mock_process_iter):
    # 模拟没有残留进程的情况
    mock_process_iter.return_value = [
        MagicMock(info={"pid": 1, "name": "not_process"}),
        MagicMock(info={"pid": 2, "name": "also_not_target"}),
        MagicMock()
    ]
 
    CustomProcess.kill_residual_process("target_process")
 
    # 确保kill_process没有被调用
    mock_process_iter.assert_called_once()
    mock_kill_process.assert_not_called()
 
 
@patch("psutil.process_iter")
@patch("ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_process")
def test_check_env_with_residual_process(mock_kill_process, mock_process_iter):
    # 模拟有残留进程的情况
    mock_process_iter.return_value = [
        MagicMock(info={"pid": 1, "name": "not_target_process"}),
        MagicMock(info={"pid": 2, "name": "target_process"}),
        MagicMock(info={"pid": 3, "name": "another_target_process"})
    ]
 
    CustomProcess.kill_residual_process("target_process,another_target_process")
 
    # 确保kill_process被调用
    mock_kill_process.assert_any_call("target_process")
    mock_kill_process.assert_any_call("another_target_process")
 
 
@patch("psutil.process_iter")
@patch("ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_process")
def test_check_env_kill_process_exception(mock_kill_process, mock_process_iter):
    # 模拟在尝试杀死进程时发生异常的情况
    mock_process_iter.return_value = [
        MagicMock(info={"pid": 1, "name": "target_process"})
    ]
    mock_kill_process.side_effect = Exception("Failed to kill process")
 
    CustomProcess.kill_residual_process("target_process")
 
    # 确保kill_process被调用，并且异常被捕获
    mock_kill_process.assert_called_once_with("target_process")
 
 
# 测试用例1：测试process_name存在且check_env成功的情况
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.CustomProcess.kill_residual_process')
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.subprocess.Popen')
def test_run_process_name_exists_and_check_env_success(mock_popen, mock_before_run, mock_check_env):
    process = CustomProcess()
    process.process_name = 'test_process'
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.run()
    mock_check_env.assert_called_once_with('test_process')
    mock_before_run.assert_called_once()
 
 
# 测试用例2：测试process_name存在但check_env失败的情况
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.CustomProcess.kill_residual_process')
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.subprocess.Popen')
def test_run_process_name_exists_and_check_env_fail(mock_popen, mock_before_run, mock_check_env):
    process = CustomProcess()
    process.process_name = 'test_process'
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    mock_check_env.side_effect = Exception('kill_residual_process failed')
    process.run()
    mock_check_env.assert_called_once_with('test_process')
    mock_before_run.assert_called_once()
    mock_popen.assert_called_once()
 
 
# 测试用例3：测试process_name不存在的情况
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.subprocess.Popen')
def test_run_process_name_not_exists(mock_popen, mock_before_run):
    process = CustomProcess()
    process.process_name = None
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.run()
    mock_before_run.assert_called_once()
 
 
# 测试用例4：测试subprocess.Popen抛出OSError的情况
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.subprocess.Popen')
def test_run_subprocess_popen_os_error(mock_popen, mock_before_run):
    process = CustomProcess()
    process.process_name = None
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    mock_popen.side_effect = OSError('subprocess.Popen failed')
    with pytest.raises(OSError) as e:
        process.run()
    assert str(e.value) == 'subprocess.Popen failed'
    mock_before_run.assert_called_once()
 
 
# 测试用例1：测试run_log为None的情况
def test_get_log_run_log_none():
    process = CustomProcess()
    process.run_log = None
    assert process.get_log() is None
 
 
# 测试用例2：测试run_log文件不存在的情况
@patch('pathlib.Path.exists', return_value=False)
def test_get_log_run_log_not_exists(mock_exists):
    process = CustomProcess()
    process.run_log = 'nonexistent.log'
    assert process.get_log() is None
 

class TestCustomProcessSupplement:
    def test_get_log_file_not_found(self):
        """测试get_log方法处理文件不存在的情况"""
        process = CustomProcess()
        process.run_log = "/nonexistent/path/test.log"
        
        result = process.get_log()
        
        assert result is None
    

class TestSplitMergedArgs:
    """测试 _split_merged_args 方法的各种场景"""

    def test_split_json_with_double_quotes(self):
        """测试拆分双引号包裹的JSON参数"""
        process = CustomProcess()
        process.command = ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']
        process._split_merged_args()
        assert process.command == ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']

    def test_split_merged_arg_with_double_quotes(self):
        """测试拆分合并的参数（双引号包裹JSON）"""
        process = CustomProcess()
        process.command = ['--compilation-config \'{"cudagraph_mode": "FULL_DECODE_ONLY"}\'']
        process._split_merged_args()
        assert process.command == ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']

    def test_split_merged_arg_with_single_quotes(self):
        """测试拆分合并的参数（单引号包裹JSON）"""
        process = CustomProcess()
        process.command = ["--compilation-config '{\"cudagraph_mode\": \"FULL_DECODE_ONLY\"}'"]
        process._split_merged_args()
        assert process.command == ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']

    def test_split_merged_arg_with_escaped_quotes(self):
        """测试拆分合并的参数（转义引号JSON）"""
        process = CustomProcess()
        process.command = ['--compilation-config \'{"cudagraph_mode": \"FULL_DECODE_ONLY\"}\'']
        process._split_merged_args()
        assert process.command == ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']

    def test_split_merged_arg_with_fullwidth_quotes(self):
        """测试拆分合并的参数（全角引号JSON）"""
        process = CustomProcess()
        process.command = ['--compilation-config \u201c{"cudagraph_mode": "FULL_DECODE_ONLY"}\u201d']
        process._split_merged_args()
        assert process.command == ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']

    def test_split_merged_arg_with_fullwidth_punctuation(self):
        """测试拆分合并的参数（全角标点JSON）"""
        process = CustomProcess()
        process.command = ['--compilation-config \'{"cudagraph_mode"\uff1a "FULL_DECODE_ONLY"}\'']
        process._split_merged_args()
        assert process.command == ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']

    def test_split_merged_arg_no_quotes(self):
        """测试拆分合并的参数（无引号JSON）"""
        process = CustomProcess()
        process.command = ['--compilation-config {"cudagraph_mode": "FULL_DECODE_ONLY"}']
        process._split_merged_args()
        assert process.command == ['--compilation-config', '{"cudagraph_mode": "FULL_DECODE_ONLY"}']

    def test_no_split_non_json_arg(self):
        """测试非JSON参数不拆分"""
        process = CustomProcess()
        process.command = ['--model', 'gpt2', '--port', '8000']
        process._split_merged_args()
        assert process.command == ['--model', 'gpt2', '--port', '8000']

    def test_no_split_simple_value(self):
        """测试简单值参数不拆分"""
        process = CustomProcess()
        process.command = ['--param value_without_braces']
        process._split_merged_args()
        assert process.command == ['--param value_without_braces']

    def test_split_nested_json(self):
        """测试拆分嵌套JSON参数"""
        process = CustomProcess()
        process.command = ['--config \'{"outer": {"inner": "value"}}\'']
        process._split_merged_args()
        assert process.command == ['--config', '{"outer": {"inner": "value"}}']

    def test_split_json_array(self):
        """测试拆分JSON数组参数"""
        process = CustomProcess()
        process.command = ['--config \'["item1", "item2"]\'']
        process._split_merged_args()
        # JSON数组现在会被is_json_like识别（支持dict和list）
        assert process.command == ['--config', '["item1", "item2"]']

    def test_keep_non_string_elements(self):
        """测试保留非字符串元素"""
        process = CustomProcess()
        process.command = ['--model', 'gpt2', 123, '--port']
        process._split_merged_args()
        assert process.command == ['--model', 'gpt2', 123, '--port']

    def test_split_multiple_merged_args(self):
        """测试拆分多个合并的参数"""
        process = CustomProcess()
        process.command = [
            '--compilation-config \'{"mode": "full"}\'',
            '--model',
            'gpt2',
            '--other-config \'{"key": "value"}\''
        ]
        process._split_merged_args()
        assert process.command == [
            '--compilation-config',
            '{"mode": "full"}',
            '--model',
            'gpt2',
            '--other-config',
            '{"key": "value"}'
        ]

    def test_split_arg_with_dot_in_name(self):
        """测试参数名包含点的拆分"""
        process = CustomProcess()
        process.command = ['--vllm.config \'{"key": "value"}\'']
        process._split_merged_args()
        assert process.command == ['--vllm.config', '{"key": "value"}']

    def test_split_arg_with_dash_in_name(self):
        """测试参数名包含短横线的拆分"""
        process = CustomProcess()
        process.command = ['--my-config \'{"key": "value"}\'']
        process._split_merged_args()
        assert process.command == ['--my-config', '{"key": "value"}']

    def test_empty_command(self):
        """测试空命令列表"""
        process = CustomProcess()
        process.command = []
        process._split_merged_args()
        assert process.command == []

    def test_split_with_backslash_escape(self):
        """测试带反斜杠转义的JSON"""
        process = CustomProcess()
        process.command = ['--config \'{\"path\": \"/tmp/test\"}\'']
        process._split_merged_args()
        assert process.command == ['--config', '{"path": "/tmp/test"}']

    def test_split_invalid_json_no_split(self, caplog):
        """测试非标准JSON参数 - 不包含{}不被识别为JSON，保持原样"""
        import logging
        process = CustomProcess()
        process.command = ['--config \'not_valid_json\'']
        with caplog.at_level(logging.WARNING):
            process._split_merged_args()
        # 不包含{}，is_json_like返回False，所以保持原样不拆分
        assert process.command == ['--config \'not_valid_json\'']


class TestBaseDataField:
    @pytest.mark.parametrize("target_field,expected", [
        ([], ()),
        ([OptimizerConfigField(name="field1", config_position="pos1", min=0, max=100, dtype="int")], 
         (OptimizerConfigField(name="field1", config_position="pos1", min=0, max=100, dtype="int"),)),
        (None, ())
    ])
    def test_data_field_property(self, target_field, expected):
        """测试data_field属性获取"""
        mock_config = MagicMock()
        if target_field is not None:
            mock_config.target_field = target_field
        else:
            delattr(mock_config, 'target_field')
        
        data_field = BaseDataField(config=mock_config)
        
        result = data_field.data_field
        
        assert result == expected
    
    def test_data_field_setter_add_new_field(self):
        """测试data_field属性设置器添加新字段"""
        mock_config = MagicMock()
        mock_config.target_field = [
            OptimizerConfigField(name="existing_field", config_position="existing.position", min=0, max=100, dtype="int")
        ]
        
        data_field = BaseDataField(config=mock_config)
        new_fields = (
            OptimizerConfigField(name="new_field", config_position="new.position", min=0, max=50, dtype="float"),
            OptimizerConfigField(name="existing_field", config_position="updated.position", min=0, max=200, dtype="int")
        )
        
        # 设置新字段
        data_field.data_field = new_fields
        
        # 验证只有existing_field被更新，new_field被忽略
        assert len(mock_config.target_field) == 1
        assert mock_config.target_field[0].name == "existing_field"
        assert mock_config.target_field[0].config_position == "updated.position"
        assert mock_config.target_field[0].max == 200
    
    def test_data_field_setter_empty_input(self):
        """测试data_field属性设置器使用空输入"""
        mock_config = MagicMock()
        mock_config.target_field = [
            OptimizerConfigField(name="field1", config_position="pos1", min=0, max=100, dtype="int")
        ]
        
        data_field = BaseDataField(config=mock_config)
        
        # 设置空字段
        data_field.data_field = ()
        
        # 验证原始字段没有被修改
        assert len(mock_config.target_field) == 1
        assert mock_config.target_field[0].name == "field1"
    
    def test_data_field_setter_no_target_field(self):
        """测试data_field属性设置器在config没有target_field时的情况"""
        mock_config = MagicMock()
        # 模拟config没有target_field属性
        if hasattr(mock_config, 'target_field'):
            delattr(mock_config, 'target_field')
        
        data_field = BaseDataField(config=mock_config)
        new_fields = (
            OptimizerConfigField(name="test_field", config_position="test.position", min=0, max=100, dtype="int"),
        )
        
        # 设置新字段（应该没有效果）
        data_field.data_field = new_fields
        
        # 验证config没有被修改
        assert not hasattr(mock_config, 'target_field') or mock_config.target_field == []


class TestCustomProcessStop:
    """测试 CustomProcess.stop 方法"""

    def test_stop_no_process(self):
        """测试 stop 方法 - 没有 process"""
        process = CustomProcess()
        process.process = None
        process.run_log_fp = None
        process.run_log = None
        
        # 不应该抛出异常
        process.stop()
        assert process.run_log_offset == 0

    def test_stop_process_already_exited(self):
        """测试 stop 方法 - 进程已经退出"""
        process = CustomProcess()
        process.run_log_fp = None
        process.run_log = None
        
        mock_subprocess = Mock()
        mock_subprocess.poll.return_value = 0  # 进程已退出
        process.process = mock_subprocess
        
        process.stop()
        
        mock_subprocess.poll.assert_called()
        assert process.run_log_offset == 0

    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.close_file_fp')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.remove_file')
    def test_stop_delete_log_file(self, mock_remove_file, mock_close_file_fp):
        """测试 stop 方法 - 删除日志文件"""
        process = CustomProcess()
        process.run_log_fp = 123
        process.run_log = "/tmp/test.log"
        process.process = None
        
        process.stop(del_log=True)
        
        mock_close_file_fp.assert_called_once_with(123)
        mock_remove_file.assert_called_once()

    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.close_file_fp')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.remove_file')
    def test_stop_keep_log_file(self, mock_remove_file, mock_close_file_fp):
        """测试 stop 方法 - 不删除日志文件"""
        process = CustomProcess()
        process.run_log_fp = 123
        process.run_log = "/tmp/test.log"
        process.process = None
        
        process.stop(del_log=False)
        
        mock_close_file_fp.assert_called_once_with(123)
        mock_remove_file.assert_not_called()

    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.psutil.Process')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_children')
    def test_stop_running_process_success(self, mock_kill_children, mock_psutil_process):
        """测试 stop 方法 - 成功停止运行中的进程"""
        process = CustomProcess()
        process.run_log_fp = None
        process.run_log = None
        
        # 模拟进程正在运行
        mock_subprocess = Mock()
        mock_subprocess.poll.return_value = None  # 进程正在运行
        mock_subprocess.pid = 12345
        mock_subprocess.wait.return_value = None  # wait 成功
        process.process = mock_subprocess
        
        # 模拟 poll 后返回非 None 表示进程已终止
        mock_subprocess.poll.side_effect = [None, 0]
        
        # 模拟 psutil.Process
        mock_proc_instance = Mock()
        mock_proc_instance.children.return_value = []
        mock_psutil_process.return_value = mock_proc_instance
        
        process.stop()
        
        mock_subprocess.kill.assert_called_once()
        mock_kill_children.assert_called_once()

    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.psutil.Process')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_children')
    def test_stop_process_timeout(self, mock_kill_children, mock_psutil_process):
        """测试 stop 方法 - 进程停止超时后发送信号"""
        process = CustomProcess()
        process.run_log_fp = None
        process.run_log = None
        
        # 模拟进程正在运行
        mock_subprocess = Mock()
        mock_subprocess.poll.return_value = None
        mock_subprocess.pid = 12345
        mock_subprocess.wait.side_effect = subprocess.TimeoutExpired("cmd", 10)
        process.process = mock_subprocess
        
        # 模拟 poll 后返回非 None 表示进程已终止
        mock_subprocess.poll.side_effect = [None, 0]
        
        # 模拟 psutil.Process
        mock_proc_instance = Mock()
        mock_proc_instance.children.return_value = []
        mock_psutil_process.return_value = mock_proc_instance
        
        process.stop()
        
        mock_subprocess.kill.assert_called_once()
        mock_subprocess.send_signal.assert_called_once_with(9)
        mock_kill_children.assert_called_once()

    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.psutil.Process')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_children')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.logger')
    def test_stop_process_exception(self, mock_logger, mock_kill_children, mock_psutil_process):
        """测试 stop 方法 - 停止进程时发生异常"""
        process = CustomProcess()
        process.run_log_fp = None
        process.run_log = None
        
        # 模拟进程正在运行
        mock_subprocess = Mock()
        mock_subprocess.poll.return_value = None
        mock_subprocess.pid = 12345
        process.process = mock_subprocess
        
        # 模拟 psutil.Process 抛出异常
        mock_psutil_process.side_effect = psutil.NoSuchProcess(12345)
        
        process.stop()
        
        # 验证异常被捕获并记录
        mock_logger.error.assert_called()

    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.psutil.Process')
    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_children')
    def test_stop_process_with_children(self, mock_kill_children, mock_psutil_process):
        """测试 stop 方法 - 停止有子进程的进程"""
        process = CustomProcess()
        process.run_log_fp = None
        process.run_log = None
        
        # 模拟进程正在运行
        mock_subprocess = Mock()
        mock_subprocess.poll.return_value = None
        mock_subprocess.pid = 12345
        mock_subprocess.wait.return_value = None
        process.process = mock_subprocess
        
        # 模拟 poll 后返回非 None 表示进程已终止
        mock_subprocess.poll.side_effect = [None, 0]
        
        # 模拟 psutil.Process 和子进程
        mock_child1 = Mock()
        mock_child2 = Mock()
        mock_proc_instance = Mock()
        mock_proc_instance.children.return_value = [mock_child1, mock_child2]
        mock_psutil_process.return_value = mock_proc_instance
        
        process.stop()
        
        mock_subprocess.kill.assert_called_once()
        mock_kill_children.assert_called_once_with([mock_child1, mock_child2])

    @patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.close_file_fp')
    def test_stop_process_shutdown_failed(self, mock_close_file_fp):
        """测试 stop 方法 - 进程停止失败"""
        process = CustomProcess()
        process.run_log_fp = None
        process.run_log = None
        
        # 模拟进程正在运行
        mock_subprocess = Mock()
        mock_subprocess.poll.return_value = None  # 进程一直运行
        mock_subprocess.pid = 12345
        process.process = mock_subprocess
        
        with patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.psutil.Process') as mock_psutil:
            mock_proc_instance = Mock()
            mock_proc_instance.children.return_value = []
            mock_psutil.return_value = mock_proc_instance
            
            with patch('ms_serviceparam_optimizer.optimizer.interfaces.custom_process.kill_children'):
                process.stop()
        
        # 验证 kill 被调用
        mock_subprocess.kill.assert_called_once()