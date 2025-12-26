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
import pandas as pd
from modelevalstate.inference.data_format_v1 import BatchField, RequestField
from modelevalstate.inference.dataset import DataProcessor, InputData, CustomLabelEncoder,\
      preset_category_data, CustomOneHotEncoder
from modelevalstate.inference.file_reader import FileHanlder


def test_preprocessor(static_file):
    custom_encoder = CustomLabelEncoder(preset_category_data)
    custom_encoder.fit()
    processor = DataProcessor(custom_encoder)
    fh = FileHanlder(static_file)
    fh.load_static_data()
    input_data = InputData(
        batch_field=BatchField("decode", 20, 20.0, 580.0, 29.0),
        request_field=(
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
        ),
        model_op_field=fh.get_op_field("decode", 29, 29, fh.prefill_op_data, fh.decode_op_data),
        model_struct_field=fh.model_struct_info,
        model_config_field=fh.model_config_info,
        mindie_field=fh.mindie_info,
        env_field=fh.env_info,
        hardware_field=fh.hardware
    )
    result = processor.preprocessor(input_data)
    assert len(result) == 902


def test_preprocessor_no_model_op_field(static_file):
    custom_encoder = CustomLabelEncoder(preset_category_data)
    custom_encoder.fit()
    processor = DataProcessor(custom_encoder)
    fh = FileHanlder(static_file)
    fh.load_static_data()
    input_data = InputData(
        batch_field=BatchField("decode", 20, 20.0, 580.0, 29.0),
        request_field=(
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
            RequestField(29.0, 1, 2),
        )
    )
    result = processor.preprocessor(input_data)
    assert len(result) == 160


def test_custom_one_hot_encoder():
    custom_encoder = CustomOneHotEncoder(preset_category_data)
    custom_encoder.fit()
    df = pd.DataFrame(
        {"batch_stage": ['prefill', 'decode'],
         "hidden_act": ["silu", "gelu_pytorch_tanh"],
         "model_type": ["bloom", "codeshell", ],
         "torch_dtype": ["float16", "float32", ],
         "quantize": ["w8a8", "w8a8s"],
         "kv_quant_type": ["c8", "c8"],
         "group_size": ["0", "64", ],
         "reduce_quant_type": ["per_channel", "per_channel"]
         }
    )
    result = custom_encoder.transformer(df)
    assert result.shape == (2, 75)
    data_column = ["batch_stage", "hidden_act", "model_type", "torch_dtype", "quantize", "kv_quant_type",
                   "group_size", "reduce_quant_type"]
    data = ['prefill', "silu", "bloom", "float16", "w8a8", "c8", "0", "per_channel"]
    new_data, new_data_column = custom_encoder.transformer_optimize(data, data_column)
    assert len(new_data) == 75
    assert len(new_data_column) == 75