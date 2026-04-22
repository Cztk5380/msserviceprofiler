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
import re
import subprocess
import tempfile
import time
from math import isnan, isinf
from pathlib import Path
from typing import Any, Tuple, Optional, List

import psutil
from loguru import logger
from msguard.security import open_s

from ...config.base_config import CUSTOM_OUTPUT, MODEL_EVAL_STATE_CONFIG_PATH, \
    ms_serviceparam_optimizer_config_path
from ..utils import close_file_fp, remove_file, kill_children, \
    backup, kill_process

# 字段名到 CLI 参数名的映射，用于在移除无效值时同步移除对应的 CLI flag
FIELD_TO_CLI_FLAG = {
    "REQUESTRATE": "--request-rate",
}

# 值为非正数（≤0）时应视为无效、移除 CLI 参数的字段集合
# 注意：非正数过滤是特定字段的语义约束，并非通用行为
NON_POSITIVE_INVALID_FIELDS = frozenset(FIELD_TO_CLI_FLAG.keys())

class CustomProcess:
    from ...config.config import OptimizerConfigField

    def __init__(self, bak_path: Optional[Path] = None, command: Optional[List[str]] = None,
                 work_path: Optional[Path] = None, print_log: bool = False,
                 process_name: str = ""):
        self.command = command
        self.bak_path = bak_path
        self.work_path = work_path if work_path else os.getcwd()
        self.run_log = None
        self.run_log_offset = None
        self.run_log_fp = None
        self.process = None
        self.print_log = print_log
        self.process_name = process_name
        self.env = os.environ.copy()
        from ...config.constant import ProcessState, Stage
        self._process_stage = ProcessState(stage=Stage.stop)

    @property
    def process_stage(self):
        return self._process_stage
    
    @process_stage.setter
    def process_stage(self, value):
        if value.stage == self._process_stage.stage:
            return
        self._process_stage = value

    @staticmethod
    def kill_residual_process(process_name):
        """
        检查环境，查看是否有残留任务  清理残留任务
        """
        logger.debug("check env")
        _residual_process = []
        _all_process_name = process_name.split(",")
        for proc in psutil.process_iter(["pid", "name"]):
            if not hasattr(proc, "info"):
                continue
            _proc_flag = []
            for p in _all_process_name:
                if p not in proc.info["name"]:
                    _proc_flag.append(True)
                else:
                    _proc_flag.append(False)
            if all(_proc_flag):
                continue
            _residual_process.append(proc)
        if _residual_process:
            logger.debug("kill residual_process")
            for _p_name in _all_process_name:
                try:
                    kill_process(_p_name)
                except Exception as e:
                    logger.error(f"Failed to kill process. {e}")
        time.sleep(1)


    def _split_merged_args(self):
        """
        将合并的参数拆分成独立的部分。
        例如：'--compilation-config \'{"cudagraph_mode": "FULL_DECODE_ONLY"}\'' 
        拆分为：'--compilation-config' 和 '{"cudagraph_mode": "FULL_DECODE_ONLY"}'
        
        这解决了 vllm 参数解析器将 JSON 键名中的下划线转换为短横线的问题。
        兼容所有 JSON 类参数输入形式：裸 JSON/引号包裹 JSON/转义 JSON/全角符号 JSON。
        不依赖硬编码的 JSON 参数列表，基于参数值的格式自动判断是否需要拆分处理。
        """
        import re
        import json
        
        def clean_json_string(json_str):
            """
            通用JSON字符串清理：仅基于语法清理，不耦合任何参数名
            处理：转义符、外层引号（单/双/全角）、全角符号、多余空格
            """
            # 1. 还原转义字符（\\" → "，\\\\ → \）
            json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
            # 2. 移除首尾的各类引号和多余空格
            json_str = json_str.strip().strip("'").strip('"').strip("\u2018").strip("\u2019").strip("\u201c").strip("\u201d")
            # 3. 全角符号转半角（中文标点→英文标点）
            json_str = json_str.replace("\uff0c", ",").replace("\uff1a", ":").replace("\uff08", "(").replace("\uff09", ")")
            return json_str
        
        def is_json_like(value):
            """
            判断字符串是否为JSON格式（仅基于语法特征，无参数耦合）
            特征：包含 {} 且能通过JSON解析（或清理后能解析）
            """
            cleaned = clean_json_string(value)
            try:
                parsed = json.loads(cleaned)
                return isinstance(parsed, (dict, list))
            except (json.JSONDecodeError, ValueError, TypeError):
                return False
        
        new_command = []
        i = 0
        while i < len(self.command):
            cmd_element = self.command[i]
            if not isinstance(cmd_element, str):
                new_command.append(cmd_element)
                i += 1
                continue
            
            # 匹配模式：--参数名 空格 引号...引号
            # 使用 \S+ 来匹配参数名（包括点和其他字符）
            match = re.match(r'^(-\S+)\s+', cmd_element)
            if not match:
                new_command.append(cmd_element)
                i += 1
                continue
            
            param_name = match.group(1)
            rest = cmd_element[match.end():]
            
            if not rest:
                new_command.append(cmd_element)
                i += 1
                continue
            
            # 判断是否为 JSON 格式（不依赖硬编码的参数列表）
            if not is_json_like(rest):
                # 非 JSON 格式，保持原样
                new_command.append(cmd_element)
                i += 1
                continue
            
            # 查找第一个引号
            first_char = rest[0]
            if first_char not in ('"', "'"):
                # 没有引号，直接尝试拆分
                cleaned_value = clean_json_string(rest)
                if is_json_like(rest):
                    new_command.append(param_name)
                    new_command.append(cleaned_value)
                    logger.debug(f"[FIX] Split merged arg (no quotes, valid JSON): {param_name} + {cleaned_value}")
                else:
                    new_command.append(cmd_element)
                i += 1
                continue
            
            # 查找最后一个匹配的引号
            last_idx = rest.rfind(first_char)
            if last_idx <= 0:
                new_command.append(cmd_element)
                i += 1
                continue
            
            json_value = rest[1:last_idx]
            
            # 清理JSON字符串
            cleaned_value = clean_json_string(json_value)
            
            # 尝试拆分，即使不是标准 JSON 也让 vllm 自行处理
            new_command.append(param_name)
            new_command.append(cleaned_value)
            if is_json_like(json_value):
                logger.debug(f"[FIX] Split merged arg (valid JSON): {param_name} + {cleaned_value}")
            else:
                logger.warning(f"[FIX] Non-standard JSON param (vllm may parse it): {param_name} = {cleaned_value}")
            i += 1
        
        self.command = new_command

    def backup(self):
        # 备份操作，默认备份日志
        backup(self.run_log, self.bak_path, self.__class__.__name__)

    def before_run(self, run_params: Optional[Tuple[OptimizerConfigField, ...]] = None):
        from ...config.config import get_settings
        """
        运行命令前的准备工作
        Args:
            run_params: 调优参数列表，元组，每一个元素的value和config position进行定义
        """
        self.run_log_fp, self.run_log = tempfile.mkstemp(prefix="ms_serviceparam_optimizer_")
        self.run_log_offset = 0
        if not run_params:
            return
        for k in run_params:
            if k.config_position == "env":
                # env 类型的数据，设置环境变量和更新命令中包含的变量,设置时全部为大写
                _env_name = k.name.upper().strip()
                _var_name = f"${_env_name}"
                
                # 检查值是否为空/无效
                if isinstance(k.value, str):
                    value_flag = k.value is None or not k.value.strip()
                else:
                    value_flag = k.value is None or isnan(k.value) or isinf(k.value)
                
                if value_flag:
                    # 值为空时，从环境变量中删除，不设置空值
                    if _env_name in self.env:
                        del self.env[_env_name]
                        logger.debug(f"Removed empty env var: {_env_name}")
                else:
                    # 值有效时，设置环境变量
                    self.env[_env_name] = str(k.value)
                
                # 处理命令行中的变量引用
                if _var_name not in self.command:
                    continue
                _i = self.command.index(_var_name)
                _cli_flag = FIELD_TO_CLI_FLAG.get(_env_name)
                # 特定字段（如 REQUESTRATE）值为非正数时视为无效，避免传入 benchmark 导致断言错误
                if not value_flag and isinstance(k.value, (int, float)) and k.value <= 0:
                    if _env_name in NON_POSITIVE_INVALID_FIELDS:
                        value_flag = True
                if value_flag:
                    self.command.pop(_i)
                    if _cli_flag and _i > 0 and self.command[_i - 1] == _cli_flag:
                        self.command.pop(_i - 1)
                else:
                    self.command[_i] = str(k.value)
        
        # 对 others 字段中的自定义变量进行替换
        # 支持在 others 参数中使用 $VAR_NAME 格式的自定义变量
        # 例如: --speculative-config '{"num_speculative_tokens": $NUM_VAR,"method":"deepseek_mtp"}'
        # 注意：这里处理所有参数（包括 config_position="env" 的变量），因为原始代码的精确匹配替换
        # 无法处理嵌套在字符串内部的变量（如 JSON 格式参数中的变量）
        for k in run_params:
            _var_name = f"${k.name.upper().strip()}"
            # 检查变量值是否有效 - Handle string values, don't call isnan/isinf on strings
            if isinstance(k.value, str):
                value_flag = k.value is None or not k.value.strip()
            else:
                value_flag = k.value is None or isnan(k.value) or isinf(k.value)
            if value_flag:
                continue
            # 在命令的每个元素中替换变量（包括 others 字段中的变量）
            # 使用 while 循环确保替换所有出现的变量（一个元素中可能出现多次）
            pattern = re.compile(rf'(?<![A-Z0-9_]){re.escape(_var_name)}(?![A-Z0-9_])')
            for i, cmd_element in enumerate(self.command):
                if isinstance(cmd_element, str):
                    self.command[i] = pattern.sub(str(k.value), cmd_element)
        
        # 修复：将合并的参数拆分成独立的部分
        # 例如：'--compilation-config \'{"cudagraph_mode": "FULL_DECODE_ONLY"}\'' 
        # 拆分为：'--compilation-config' 和 '{"cudagraph_mode": "FULL_DECODE_ONLY"}'
        self._split_merged_args()
        
        if CUSTOM_OUTPUT not in self.env:
            # 设置输出目录
            self.env[CUSTOM_OUTPUT] = str(get_settings().output)
        # 设置读取的json文件
        if MODEL_EVAL_STATE_CONFIG_PATH not in self.env:
            self.env[MODEL_EVAL_STATE_CONFIG_PATH] = str(ms_serviceparam_optimizer_config_path)
                

    def run(self, run_params: Optional[Tuple[OptimizerConfigField, ...]] = None, **kwargs):
        # 启动测试
        if self.process_name:
            try:
                self.kill_residual_process(self.process_name)
            except Exception as e:
                logger.error(f"Failed to kill residual process. {e}")
        self.before_run(run_params)
        
        for i, v in enumerate(self.command):
            if not v.strip():
                continue
            if '-' not in v and '--' not in v:
                continue
            if v in self.command[:i]:
                logger.warning("{} field appears multiple times in the command. please confirm.", v)
        for k, v in self.env.items():
            if isinstance(k, str) and isinstance(v, str):
                continue
            else:
                logger.error(f"Possible Problem with Environment Variable Type. "
                             f"env: {k}={v}, k type: {type(k)}, v type: {type(v)}")
        from ...config.constant import ProcessState, Stage
        try:
            self.process = subprocess.Popen(self.command, env=self.env, stdout=self.run_log_fp,
                                            stderr=subprocess.STDOUT, cwd=self.work_path)
            self.process_stage = ProcessState(stage=Stage.start)
        except OSError as e:
            logger.error(f"Failed to run {self.command}. error {e}")
            raise e
        logger.info(f"Start running the command: {' '.join(self.command)}, log file: {self.run_log}")

    def get_log(self):
        output = None
        if not self.run_log:
            return output
        run_log_path = Path(self.run_log)
        if run_log_path.exists():
            try:
                with open_s(run_log_path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self.run_log_offset)
                    output = f.read()
                    self.run_log_offset = f.tell()
            except (UnicodeError, OSError) as e:
                logger.error(f"Failed read {self.command} log. error {e}")
        return output

    def health(self):
        from ...config.constant import ProcessState, Stage
        """
        检查任务是否运行成功
        Returns: 返回bool值，检查程序是否成功启动
        """
        if self.print_log:
            output = self.get_log()
            logger.debug(output)
        if self.process.poll() is None:
            return ProcessState(stage=Stage.running)
        elif self.process.poll() == 0:
            return ProcessState(stage=Stage.stop)
        else:
            return ProcessState(stage=Stage.error, info=f"Failed in run {self.command!r}. \
                                        return code: {self.process.returncode}. log: {self.run_log}")

    def stop(self, del_log: bool = True):
        from ...config.constant import ProcessState, Stage
        self.run_log_offset = 0
        close_file_fp(self.run_log_fp)
        if del_log and self.run_log:
            remove_file(Path(self.run_log))
        if not self.process:
            return
        _process_state = self.process.poll()
        if _process_state is not None:
            self.process_stage = ProcessState(stage=Stage.stop)
            logger.info(f"The program has exited. exit_code: {_process_state}")
            return
        try:
            children = psutil.Process(self.process.pid).children(recursive=True)
            self.process.kill()
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                self.process.send_signal(9)
            if self.process.poll() is not None:
                logger.debug(f"The {self.process.pid} process has been shut down.")
            else:
                logger.error(f"The {self.process.pid} process shutdown failed.")
            kill_children(children)
            self.process_stage = ProcessState(stage=Stage.stop)
        except Exception as e:
            logger.error(f"Failed to stop simulator process. {e}")
            self.process_stage = ProcessState(stage=Stage.error, info=f"Failed to stop simulator process. {e}")

    def get_last_log(self, number: int = 5):
        output = None
        if not self.run_log:
            return output
        run_log_path = Path(self.run_log)
        if run_log_path.exists():
            file_lines = []
            encodings_to_try = ["utf-8", "latin-1", "gbk", "cp1252"]
            
            for encoding in encodings_to_try:
                try:
                    with open_s(run_log_path, "r", encoding=encoding, errors="replace") as f:
                        file_lines = f.readlines()
                    break
                except (UnicodeError, OSError) as e:
                    if encoding == encodings_to_try[-1]:
                        logger.error(f"Failed read {self.command} log after trying all encodings. error {e}")
                    continue
            number = min(number, len(file_lines))
            output = '\n'.join(file_lines[-number:])
        return output


class BaseDataField:
    from ...config.config import OptimizerConfigField

    def __init__(self, config: Optional[Any] = None):
        from ...config.config import get_settings
        if config:
            self.config = config
        else:
            settings = get_settings()
            self.config = settings.ais_bench
 
    @property
    def data_field(self) -> Tuple[OptimizerConfigField, ...]:
        """
        获取data field 属性
        """
        if hasattr(self.config, "target_field") and self.config.target_field:
            return tuple(self.config.target_field)
        return ()
 
    @data_field.setter
    def data_field(self, value: Tuple[OptimizerConfigField] = ()) -> None:
        """
        提供新的数据，更新替换data field属性。
        """
        _default_name = []
        if hasattr(self.config, "target_field") and self.config.target_field:
            _default_name = [_f.name for _f in self.config.target_field]
        for _field in value:
            if _field.name not in _default_name:
                continue
            _index = _default_name.index(_field.name)
            self.config.target_field[_index] = _field
