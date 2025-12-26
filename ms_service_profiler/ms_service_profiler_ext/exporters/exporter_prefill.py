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

from ms_service_profiler.exporters.base import ExporterBase

from ..common.utils import logger
from ..common.split_utils import get_service_type


class ExporterPrefill(ExporterBase):
    name = "prefill_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        cls.args.batch_size = cls.args.prefill_batch_size
        cls.args.batch_num = cls.args.prefill_number
        cls.args.rid = cls.args.prefill_rid
        df = data.get('tx_data_df')
        if df is None:
            logger.error("The data is empty, please check")
            return
        processor = get_service_type(df)
        processor.initialize(cls.args)
        processor.run_split(df, "Prefill")
        
        logger.info("Export prefill data successfully.")