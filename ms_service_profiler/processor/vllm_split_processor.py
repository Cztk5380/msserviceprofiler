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


from .split_base_processor import BaseFrameworkProcessor


class VllmProcessor(BaseFrameworkProcessor):
    batch_start_name = "batchFrameworkProcessing"
    batch_end_name = "forward"
    http_start_name = "httpReq"
    http_end_name = "httpRes"
    key_name = "forward"
    all_time_name = "AllTime"
    http_list = ["httpReq", "encode", "decodeEnd", "httpRes"]
    name_list = [batch_start_name, "preprocess", batch_end_name]
    filter_list = [http_start_name, http_end_name, all_time_name]
    name_list = name_list + http_list

    @classmethod
    def initialize(cls, args):
        cls.args = args