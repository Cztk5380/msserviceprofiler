# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import (
    write_result_to_csv, write_result_to_db,
    check_domain_valid, CURVE_VIEW_NAME_LIST
)
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import key_except


class ExporterCoordinator(ExporterBase):
    name = "coordinator"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.info)
    @key_except('domain', 'name', ignore=True, msg="ignoring current exporter by default.")
    def export(cls, data) -> None:
        if "csv" not in cls.args.format and "db" not in cls.args.format:
            return

        df = data.get("tx_data_df")
        if df is None:
            logger.warning("The data is empty, please check")
            return
        print(df)
        breakpoint()