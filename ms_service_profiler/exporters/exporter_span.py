# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
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
from typing import List

import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import write_result_to_csv, get_filter_span_df
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.constant import US_PER_MS

RENAME_COLUMNS = {
    "name": "span_name",
    "during_time": "during_time(ms)"
}
# 默认统计的Span - 兼容mindIE/vllm
DEFAULT_SPAN = ['forward', 'BatchSchedule', 'batchFrameworkProcessing']
REQUIRED_COLUMNS = ["name", "start_datetime", "end_datetime", "during_time", "hostname", "pid"]
TIME_COLUMNS = ["during_time"]
SPAN_OUTPUT_DIR = "span_info"


class ExporterSpan(ExporterBase):
    name = "span"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.debug)
    def export(cls, data) -> None:
        df = data.get("tx_data_df")
        if df is None:
            logger.warning("There is no service prof data, span data will not be generated. please check.")
            return

        try:
            span_df = cls._prepare_span_data(df)
            if span_df.empty:
                logger.warning("There is no span data after filtering, span data will not be generated. please check.")
                return

            cls._export_span_data(span_df)
        except Exception as e:
            logger.warning(f"Failed to export span data, error: {e}", exc_info=True)

    @classmethod
    def _prepare_span_data(cls, df: pd.DataFrame) -> pd.DataFrame:
        """准备span数据"""
        span_df = get_filter_span_df(df, REQUIRED_COLUMNS, TIME_COLUMNS)
        span_names = cls._get_span_names()

        if cls.args.span:
            available_spans = span_df['name'].unique().tolist()
            missing_spans = [span for span in cls.args.span if span not in available_spans]

            if missing_spans:
                logger.warning(f"Span '{', '.join(missing_spans)}' does not exist in data, please check span name.")

        return span_df[span_df['name'].isin(span_names)]

    @classmethod
    def _get_span_names(cls) -> List[str]:
        """获取需要统计的span名称列表"""
        if cls.args.span:
            return list(set(DEFAULT_SPAN + cls.args.span))
        return DEFAULT_SPAN

    @classmethod
    def _export_span_data(cls, span_df: pd.DataFrame) -> None:
        """导出span数据到CSV文件"""
        output_path = os.path.join(cls.args.output_path, SPAN_OUTPUT_DIR)
        os.makedirs(output_path, mode=0o750, exist_ok=True)
        logger.info(f"Saving spans to {output_path}")

        for span_name, group_df in span_df.groupby('name'):
            if 'during_time' in group_df:
                group_df['during_time'] = group_df['during_time'].div(US_PER_MS).map(lambda x: f"{x:.3f}")
            write_result_to_csv(group_df, output_path, span_name, RENAME_COLUMNS)