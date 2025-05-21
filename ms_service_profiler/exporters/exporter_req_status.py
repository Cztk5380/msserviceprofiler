# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from enum import Enum
from pathlib import Path

import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.plugins.plugin_req_status import ReqStatus
from ms_service_profiler.exporters.utils import add_table_into_visual_db, create_sqlite_views, check_domain_valid
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger


class ExporterReqStatus(ExporterBase):
    name = "req_status"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.info)
    def export(cls, data) -> None:
        if 'db' in cls.args.format:
            df = data.get('tx_data_df')
            if df is None:
                logger.error("The data is empty, please check")
                return

            if check_domain_valid(df, ['Request'], 'request_status') is False:
                return

            metrics = data.get('metric_data_df')
            req_status_cols = [col for col in metrics.columns if col in ReqStatus.__members__]

            df = metrics[req_status_cols].astype(int)
            df.insert(0, 'timestamp', metrics['start_datetime'])

            # 默认会从db文件中筛选下述列进行展示，如不存在该列需要补齐
            show_columns = []
            for status in ReqStatus:
                show_columns.append(status.name)

            for column_name in show_columns:
                if column_name not in df.columns:
                    df = df.assign(**{column_name: [None] * len(df)})

            add_table_into_visual_db(df, 'request_status')
            create_sqlite_views('Request_Status', CREATE_REQUEST_STATE_VIEW_SQL)


CREATE_REQUEST_STATE_VIEW_SQL = """
    CREATE VIEW Request_Status_curve AS
    SELECT
        substr( timestamp, 1, 10 ) || ' ' || substr( timestamp, 12, 8 ) || '.' || substr( timestamp, 21, 6 ) AS time,
        WAITING, PENDING, RUNNING 
    FROM
        request_status 
    ORDER BY
        time ASC
"""
