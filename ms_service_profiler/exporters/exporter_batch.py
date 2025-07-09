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


def filter_batch_df(batch_name, batch_df):
    batch_df['batch_size'] = batch_df['batch_size'].astype(float)
    batch_df = batch_df[batch_df['name'].isin(['modelExec', batch_name])]
    ori_columns = ['name', 'res_list', 'start_time', 'end_time', 'batch_size', \
        'batch_type', 'during_time']
    existing_columns = [col for col in ori_columns if col in batch_df.columns]
    batch_df = batch_df[existing_columns]
    batch_df['during_time'] = batch_df['during_time'] / US_PER_MS
    batch_df['start_time'] = batch_df['start_time'] // US_PER_MS
    batch_df['end_time'] = batch_df['end_time'] // US_PER_MS
    return batch_df


def get_rename_cols(ori_cols):
    rename_cols = {
        'start_time': 'start_time(ms)', 'end_time': 'end_time(ms)',
        'during_time': 'during_time(ms)'
    }
    return rename_cols


class ExporterBatchData(ExporterBase):
    name = "batch_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.info)
    @key_except('domain', 'name', ignore=True, msg="ignoring current exporter by default.")
    def export(cls, data) -> None:
        if 'csv' in cls.args.format or 'db' in cls.args.format:
            df = data.get('tx_data_df')
            if df is None:
                logger.warning("The data is empty, please check")
                return
            output = cls.args.output_path

            if check_domain_valid(df, ['ModelExecute', 'BatchSchedule'], 'batch') is False:
                return

            # 获取组batch字段名称，旧版本为BatchScheduler，新版本为batchFrameworkProcessing
            batch_name = 'BatchSchedule' if (df['name'] == 'BatchSchedule').any() else 'batchFrameworkProcessing'
            batch_df = df[df['name'].isin([batch_name, 'modelExec'])]
            if batch_df.empty:
                logger.warning("No batch data found. Please check msproftx.db.")
                return
            # 筛选显示
            batch_df = filter_batch_df(batch_name, batch_df)
            rename_cols = get_rename_cols(batch_df.columns)

            if 'db' in cls.args.format:
                df_param_list = [
                    [batch_df, 'batch'],
                    [data.get('batch_req_df'), 'batch_req'],
                    [data.get('batch_exec_df'), 'batch_exec']
                ]
                write_result_to_db(
                    df_param_list=df_param_list,
                    create_view_sql=[CREATE_BATCH_VIEW_SQL],
                    table_name='batch',
                    rename_cols=rename_cols
                )

            if 'csv' in cls.args.format:
                write_result_to_csv(batch_df, output, 'batch', rename_cols)


CREATE_BATCH_VIEW_SQL = f"""
    CREATE VIEW {CURVE_VIEW_NAME_LIST['batch']} AS
    WITH numbered_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY "start_time") - 1 AS batch_id,
            batch_size,
            batch_type
        FROM 
            batch
        WHERE 
            name in ('BatchSchedule', 'batchFrameworkProcessing')
    )
    SELECT
        batch_id,
        CASE
            WHEN batch_type = 'Prefill' THEN batch_size
            ELSE NULL
        END AS Prefill_batch_size,
        CASE
            WHEN batch_type = 'Decode' THEN batch_size
            ELSE NULL
        END AS Decode_batch_size
    FROM
        numbered_data
    ORDER BY
        batch_id;
"""