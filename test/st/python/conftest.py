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
import shutil
import uuid

import pytest
from pytest_check import check_functions, check

pytest.assume = check_functions.is_true


def pytest_addoption(parser):
    parser.addoption("--device", action="append", type=int, default=[], help="devices")
    parser.addoption(
        "--mindie-path", action="store", default="/usr/local/lib/python3.11/site-packages/mindie_llm/", help="mindie path"
    )
    parser.addoption("--dataset-path", action="store", default="/dataset", help="dataset path")
    parser.addoption("--model-path", action="store", default="/model", help="model path")
    parser.addoption(
        "--sglang-port",
        action="store",
        type=int,
        default=None,
        help="SGLang server port (default: auto 7399+pid%%10000 for concurrent runs)",
    )
    parser.addoption("--workspace", action="store", default="/workspace", help="workspace path")
    parser.addoption("--debug-mode", action="store", type=bool, default=False, help="debug")


@pytest.fixture(scope="session")
def devices(request):
    devices = request.config.getoption("--device")
    return devices if devices else [0]


@pytest.fixture(scope="session")
def mindie_path(request):
    return request.config.getoption("--mindie-path")


@pytest.fixture(scope="session")
def dataset_path(request):
    return request.config.getoption("--dataset-path")


@pytest.fixture(scope="session")
def model_path(request):
    return request.config.getoption("--model-path")


@pytest.fixture(scope="session")
def sglang_port(request):
    port = request.config.getoption("--sglang-port")
    if port is not None:
        return port
    # 多人并发时避免端口冲突：7399 + pid % 10000
    return 7399 + (os.getpid() % 10000)


@pytest.fixture(scope="session")
def workspace(request):
    workspace_path = request.config.getoption("--workspace")
    os.makedirs(workspace_path, exist_ok=True)
    return workspace_path


@pytest.fixture(scope="session")
def smokedata(workspace):
    return os.path.join(workspace, "smokedata")


@pytest.fixture(scope="session")
def debug(request):
    return request.config.getoption("--debug-mode")


@pytest.fixture(scope="function")
def tmp_workspace(debug):
    index = str(uuid.uuid4())
    workspace_path = os.path.join("/tmp/server-smoke", index)
    os.makedirs(workspace_path, exist_ok=True)
    yield workspace_path
    if not debug:
        shutil.rmtree(workspace_path, ignore_errors=True)
    else:
        print("tmp workspace is ", workspace_path)


@pytest.fixture(scope="session")
def smoke_args(devices, mindie_path, dataset_path, model_path, workspace, smokedata, debug):
    return dict(devices=devices, mindie_path=mindie_path, dataset_path=dataset_path,
                model_path=model_path, smokedata=smokedata, workspace=workspace, debug=debug)
