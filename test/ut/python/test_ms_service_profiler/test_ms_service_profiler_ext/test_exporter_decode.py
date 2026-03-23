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
import unittest
from pathlib import Path
from argparse import Namespace
import numpy as np
import pandas as pd

from ms_service_profiler.exporters.exporter_decode import ExporterDecode


class TestExporterDecodeFunction(unittest.TestCase):
    def setUp(self):
        self.data_mindie = {"tx_data_df": self.mock_data_mindie()}
        self.data_vllm = {"tx_data_df": self.mock_data_vllm()}

    def mock_data_mindie(self):
        name_list = [
            "encode", "httpReq", "batchFrameworkProcessing", "serializeExcueteMessage", "setInferBuffer",
            "grpcWriteToSlave", "deserializeExecuteRequestsForInfer", "convertTensorBatchToBackend",
            "getInputMetadata", "preprocess", "forward", "sample", "postprocess", "generateOutput",
            "processPythonExecResult", "deserializeExecuteResponse", "httpRes",
        ]
        data = {
            "name": name_list * 3,
        }
        len_data = len(data["name"])
        data["during_time"] = np.random.rand(len_data) * 1000
        data["pid"] = ["40"] * len_data
        data["tid"] = ["100"] * len_data
        data["start_time"] = np.arange(len_data) * 1000
        data["end_time"] = np.arange(len_data) * 1000 + 50
        data["start_datetime"] = ["123"] * len_data
        data["end_datetime"] = ["123"] * len_data
        data["batch_type"] = [""] * len_data
        data["rid"] = [""] * len_data
        data["batch_size"] = [None] * len_data
        data["rid_list"] = [None] * len_data
        data["token_id_list"] = [["1234", "5678"]] * len_data
        batch_indices = np.where(np.array(data["name"]) == "batchFrameworkProcessing")[0]
        forward_indices = np.where(np.array(data["name"]) == "forward")[0]
        for i, num in enumerate(batch_indices):
            data["batch_type"][num] = "Decode"
            data["batch_size"][num] = "100"
            data["rid"][num] = str(i + 1)  # 递增的 rid 值
            data["rid_list"][num] = [str(i + 1)]

        for i, num in enumerate(forward_indices):
            data["rid"][num] = str(i + 1)
            data["rid_list"][num] = [str(i + 1)]

        serialize_indices = np.where(np.array(data["name"]) == "serializeExcueteMessage")[0]
        for i in serialize_indices:
            # 找到前一个 batchFrameworkProcessing 的 end_time
            previous_batch_index = np.where(np.array(data["name"])[:i] == "batchFrameworkProcessing")[0]
            if len(previous_batch_index) > 0:
                previous_end_time = data["end_time"][previous_batch_index[-1]]
                # 确保 start_time 与前一个 end_time 之间的差值小于 100000
                data["start_time"][i] = min(data["start_time"][i], previous_end_time + 100000)
        df = pd.DataFrame(data)
        return df

    def mock_data_vllm(self):
        name_list = [
            "encode",
            "httpReq",
            "batchFrameworkProcessing",
            "preprocess",
            "forward",
            "httpRes"
        ]
        data = {
            "name": name_list * 3,
        }
        len_data = len(data["name"])
        data["during_time"] = np.random.rand(len_data) * 1000
        data["pid"] = ["40"] * len_data
        data["tid"] = ["100"] * len_data
        data["start_time"] = np.arange(len_data) * 1000
        data["end_time"] = np.arange(len_data) * 1000 + 50
        data["start_datetime"] = ["123"] * len_data
        data["end_datetime"] = ["123"] * len_data
        data["batch_type"] = [""] * len_data
        data["rid"] = [""] * len_data
        data["batch_size"] = [None] * len_data
        data["rid_list"] = [None] * len_data
        data["token_id_list"] = [["1234", "5678"]] * len_data
        batch_indices = np.where(np.array(data["name"]) == "batchFrameworkProcessing")[0]
        forward_indices = np.where(np.array(data["name"]) == "forward")[0]
        for i, num in enumerate(batch_indices):
            data["batch_type"][num] = "Decode"
            data["batch_size"][num] = "100"
            data["rid"][num] = str(i + 1)  # 递增的 rid 值
            data["rid_list"][num] = [str(i + 1)]

        for i, num in enumerate(forward_indices):
            data["rid"][num] = str(i + 1)
            data["rid_list"][num] = [str(i + 1)]

        df = pd.DataFrame(data)
        return df

    def test_exporter_decode(self):
        args = Namespace(
            output_path=os.path.join(os.getcwd(), "output"),
            log_level="debug",
            decode_batch_size=100,
            decode_number=2,
            decode_rid="-1",
        )
        try:
            os.makedirs(args.output_path, exist_ok=True)
            os.chmod(args.output_path, 0o740)
            file_path = Path(args.output_path, "decode.csv")
            ExporterDecode.initialize(args)
            ExporterDecode.export(self.data_mindie)
            self.assertTrue(file_path.is_file())
        finally:
            shutil.rmtree(args.output_path)

        try:
            os.makedirs(args.output_path, exist_ok=True)
            os.chmod(args.output_path, 0o740)
            file_path = Path(args.output_path, "decode.csv")
            ExporterDecode.initialize(args)
            ExporterDecode.export(self.data_vllm)
            self.assertTrue(file_path.is_file())
        finally:
            shutil.rmtree(args.output_path)

    def test_exporter_decode_rid(self):
        args = Namespace(
            output_path=os.path.join(os.getcwd(), "output"),
            log_level="debug",
            decode_batch_size=100,
            decode_number=2,
            decode_rid="1",
        )
        try:
            os.makedirs(args.output_path, exist_ok=True)
            os.chmod(args.output_path, 0o740)
            file_path = Path(args.output_path, "decode.csv")
            ExporterDecode.initialize(args)
            ExporterDecode.export(self.data_mindie)
            self.assertTrue(file_path.is_file())
        finally:
            shutil.rmtree(args.output_path)

        try:
            os.makedirs(args.output_path, exist_ok=True)
            os.chmod(args.output_path, 0o740)
            file_path = Path(args.output_path, "decode.csv")
            ExporterDecode.initialize(args)
            ExporterDecode.export(self.data_vllm)
            self.assertTrue(file_path.is_file())
        finally:
            shutil.rmtree(args.output_path)