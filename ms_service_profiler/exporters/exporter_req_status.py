# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import pandas as pd
import numpy as np

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.plugins.plugin_req_status import ReqStatus
from ms_service_profiler.exporters.utils import write_result_to_db, CURVE_VIEW_NAME_LIST, check_domain_valid, \
    check_columns_valid, save_dataframe_to_csv, COLUMN_CONST
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import key_except


class ExporterReqStatus(ExporterBase):
    name = "req_status"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.debug)
    @key_except(COLUMN_CONST.DOMAIN_COLUMN, COLUMN_CONST.NAME_COLUMN, \
        ignore=True, msg="ignoring current exporter by default.")
    def export(cls, data) -> None:
        if 'db' not in cls.args.format and 'csv' not in cls.args.format:
            return

        if cls.valid_for_csv_output(data):
            df = data.get('tx_data_df')
            need_columns = [COLUMN_CONST.HOSTUID_COLUMN, COLUMN_CONST.PID_COLUMN, COLUMN_CONST.START_TIME_COLUMN, \
                COLUMN_CONST.DOMAIN_COLUMN, COLUMN_CONST.NAME_COLUMN, COLUMN_CONST.STATUS_COLUMN, \
                    COLUMN_CONST.QUEUESIZE_COLUMN]

            mask = (
                (df[COLUMN_CONST.DOMAIN_COLUMN] == 'Schedule') &
                (df[COLUMN_CONST.NAME_COLUMN] == 'Queue') &
                (df[COLUMN_CONST.STATUS_COLUMN].isin(['waiting', 'running', 'swapped']))
            )
            df = df.loc[mask, need_columns]
            df['waiting'] = np.where(df[COLUMN_CONST.STATUS_COLUMN] == 'waiting', \
                df[COLUMN_CONST.QUEUESIZE_COLUMN], None)
            df['running'] = np.where(df[COLUMN_CONST.STATUS_COLUMN] == 'running', \
                df[COLUMN_CONST.QUEUESIZE_COLUMN], None)
            df['swapped'] = np.where(df[COLUMN_CONST.STATUS_COLUMN] == 'swapped', \
                df[COLUMN_CONST.QUEUESIZE_COLUMN], None)

            # 增加timestamp(ms)列
            df[COLUMN_CONST.TIMESTAMP_MS_COLUMN] = (df[COLUMN_CONST.START_TIME_COLUMN] / 1000.0).round(2)

            # 增加relative_timestamp(ms)列
            df[COLUMN_CONST.RELATIVE_TIMESTAMP_MS_COLUMN] = \
                df.groupby(COLUMN_CONST.PID_COLUMN)[COLUMN_CONST.TIMESTAMP_MS_COLUMN].transform(
                    lambda x: (x - x.min()).round(2))


            desired_columns = [COLUMN_CONST.HOSTUID_COLUMN, COLUMN_CONST.PID_COLUMN, \
                COLUMN_CONST.TIMESTAMP_MS_COLUMN, COLUMN_CONST.RELATIVE_TIMESTAMP_MS_COLUMN, \
                'waiting', 'running', 'swapped']
            df = df[desired_columns]

            output = cls.args.output_path
            logger.info("Start save data to csv")
            save_dataframe_to_csv(df, output, "request_status.csv")
            logger.info('Write request status data to csv success')

        if cls.valid_for_db_output(data):
            df = data.get('tx_data_df')
            metrics = data.get('metric_data_df')

            # 处理 status 列的映射和编码
            df = cls._process_status_columns(df, metrics)

            logger.info('Start write request data to db')
            write_result_to_db(
                df_param_list=[[df, 'request_status']],
                table_name='request_status',
                create_view_sql=[cls.CREATE_REQUEST_STATE_VIEW_SQL]
            )
            logger.info('Write request data to db success')

    @classmethod
    def valid_for_csv_output(cls, data):
        df = data.get("tx_data_df")
        if df is None:
            logger.warning("There is no service prof data, request status data will not be generated. please check")
            return False

        need_columns = [COLUMN_CONST.HOSTUID_COLUMN, COLUMN_CONST.PID_COLUMN, COLUMN_CONST.START_TIME_COLUMN, \
            COLUMN_CONST.DOMAIN_COLUMN, COLUMN_CONST.NAME_COLUMN, COLUMN_CONST.STATUS_COLUMN, \
                COLUMN_CONST.QUEUESIZE_COLUMN]
        if not check_columns_valid(df, need_columns, cls.name):
            return False
        if not check_domain_valid(df, ['Schedule'], cls.name):
            return False
        return True

    @classmethod
    def valid_for_db_output(cls, data):
        df = data.get("tx_data_df")
        if df is None:
            logger.warning("There is no service prof data, request status data will not be generated. please check")
            return False

        if not check_domain_valid(df, ['Request'], 'request_status'):
            return False

        metrics = data.get('metric_data_df')
        if metrics is None:
            logger.warning("The req status prof data is empty, no request status data will generated. please check")
            return False
        return True

    @classmethod
    def _process_status_columns(cls, df, metrics):
        if COLUMN_CONST.STATUS_COLUMN in df.columns:
            df = cls._map_and_encode_status(df, metrics)
        else:
            df = cls._prepare_metrics_df(df, metrics)
        return df

    @classmethod
    def _map_and_encode_status(cls, df, metrics):
        old_status_mapping = {
            'waiting': 'WAITING',
            'running': 'RUNNING',
        }

        # 将status列的值映射到旧版状态值
        df[COLUMN_CONST.STATUS_COLUMN] = df[COLUMN_CONST.STATUS_COLUMN].map(old_status_mapping)

        # 将status列转换为one-hot编码
        df = pd.get_dummies(df[COLUMN_CONST.STATUS_COLUMN], prefix='', prefix_sep='')

        # 添加timestamp列
        df.insert(0, 'timestamp', metrics['start_datetime'])

        # 补全缺失的状态列，值为0
        for status in old_status_mapping.values():
            if status not in df.columns:
                df[status] = 0

        if 'PENDING' not in df.columns:
            df['PENDING'] = 0

        # 确保列的顺序正确
        df = df[['timestamp'] + list(old_status_mapping.values()) + ['PENDING']]
        return df

    @classmethod
    def _prepare_metrics_df(cls, df, metrics):
        req_status_cols = [col for col in metrics.columns if col in ReqStatus.__members__]
        df = metrics[req_status_cols].fillna(0).astype(int)
        df.insert(0, 'timestamp', metrics['start_datetime'])

        # 默认会从db文件中筛选下述列进行展示，如不存在该列需要补齐
        show_columns = [status.name for status in ReqStatus]

        for column_name in show_columns:
            if column_name not in df.columns:
                df = df.assign(**{column_name: [None] * len(df)})
        return df

    CREATE_REQUEST_STATE_VIEW_SQL = f"""
        CREATE VIEW {CURVE_VIEW_NAME_LIST['request_status']} AS
        SELECT
            substr( timestamp, 1, 10 ) || ' ' || substr( timestamp, 12, 8 ) || '.' || substr( timestamp, 21, 6 ) AS time,
            WAITING, PENDING, RUNNING
        FROM
            request_status
        ORDER BY
            time ASC
    """