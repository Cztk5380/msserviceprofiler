# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import json

import pandas as pd

from ms_service_profiler.parse import get_filepaths
from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.error import LoadDataError


@Task.register("data_source:db")
class DBDataSource(BaseDataSource):
    @classmethod
    def get_prof_paths(cls, input_path: str):
        file_filter = {
            "service": "ms_service_*.db"
        }

        filepaths = get_filepaths(input_path, file_filter)

        db_files = filepaths.get("service", [])
        if db_files:
            db_files = [db_files]

        return db_files

    @classmethod
    def process(cls, files):
        """
        处理一组文件，将文件内容转换为DataFrame格式，并进行数据处理和转换。
        添加hostname列到DataFrame的最前面，并将其重命名为hostuid。

        :param files: 要处理的文件列表
        :return: 一个字典，包含处理后的数据
        """
        from ms_service_profiler.parse_helper.utils import convert_db_to_df

        # 将文件内容转换为DataFrame
        df = convert_db_to_df(files)
        if df.empty:
            return dict(
                tx_data_df=pd.DataFrame(),  # 事务数据，包含hostuid列
                cpu_data_df=None,  # CPU数据（暂无）
                memory_data_df=None,  # 内存数据（暂无）
                time_info=None,  # 时间信息（暂无）
                msprof_data=[],  # msprof算子数据，是个包含路径的列表，msprof_xxxx.json
                msprof_data_df=[]  # msprof数据（DataFrame格式，暂无）
            )

        # 重置索引并重命名列
        df = df.reset_index(drop=True).rename(columns={'timestamp': 'start_time', 'endTimestamp': 'end_time'})

        # 将时间戳单位从毫秒转换为秒
        df[['start_time', 'end_time']] = df[['start_time', 'end_time']].div(1000)

        # 计算持续时间（结束时间 - 开始时间）
        df['during_time'] = df['end_time'] - df['start_time']

        # 将开始时间戳转换为本地时间（上海时区），格式化为字符串
        df['start_datetime'] = pd.to_datetime(df['start_time'], unit='us', utc=True).dt.tz_convert(
            'Asia/Shanghai').dt.strftime("%Y-%m-%d %H:%M:%S:%f")

        # 将结束时间戳转换为本地时间（上海时区），格式化为字符串
        df['end_datetime'] = pd.to_datetime(df['end_time'], unit='us', utc=True).dt.tz_convert(
            'Asia/Shanghai').dt.strftime("%Y-%m-%d %H:%M:%S:%f")

        # 定义一个函数来处理消息字段
        df['message'] = (
            df['message']
            .str.replace(r'\^', '"', regex=True)
            .where(
                lambda s: s.str.match(r'^{.*}$'),
                other=lambda s: "{" + s.str.replace(r",$", "", regex=True) + "}"
            )
            .apply(json.loads)
        )

        # 将消息字段展开为独立的列
        msg_df = pd.json_normalize(df['message'])

        # 将展开的消息数据与原始数据合并
        all_data_df = df.join(msg_df)

        # 在最前面添加hostname列，并将其重命名为hostuid
        all_data_df.insert(0, 'hostuid', df['hostname'])

        # 返回包含处理后数据的字典
        return dict(
            tx_data_df=all_data_df,  # 事务数据，包含hostuid列
            cpu_data_df=None,  # CPU数据（暂无）
            memory_data_df=None,  # 内存数据（暂无）
            time_info=None,  # 时间信息（暂无）
            msprof_data=[],  # msprof算子数据，是个包含路径的列表，msprof_xxxx.json
            msprof_data_df=[]  # msprof数据（DataFrame格式，暂无）
        )

    def load(self, prof_path):
        db_files = prof_path
        return self.process(db_files)

