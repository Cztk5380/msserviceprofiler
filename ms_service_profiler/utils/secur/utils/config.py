# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import threading

import yaml


CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'secur_config.yaml')

_config_lock = threading.Lock()
_config_local = threading.local()


def load_config():
    global _config_local

    with _config_lock:
        if not hasattr(_config_local, 'config'):
            if not os.path.exists(CONFIG_FILE):
                raise FileNotFoundError(f"Configuration file {CONFIG_FILE} not found.")
            with open(CONFIG_FILE, 'r') as f:
                try:
                    config = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML format in {CONFIG_FILE}: {e}") from e
            _config_local.config = config
            

    return _config_local.config


def get_file_size_config():
    config = load_config()

    if "PathConfig" not in config:
        raise ValueError("Cannot find PathConfig in the secur_config.yaml")

    path_config = config['PathConfig']

    if "FileSizeConfig" not in path_config:
        raise ValueError("Cannot find FileSizeConfig in the secur_config.yaml")
    
    file_size_config = path_config['FileSizeConfig']

    if "ext_mapping" not in file_size_config:
        raise ValueError("Cannot find ext_mapping in the secur_config.yaml")

    ext_mapping = file_size_config['ext_mapping']

    if not isinstance(ext_mapping, dict):
        raise ValueError("ext_mapping is not defined as a dict in the secur_config.yaml")

    file_size_config.setdefault("require_confirm", False)

    return file_size_config
