# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import json
import re

import pandas as pd
from pathlib import Path


from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.error import LoadDataError


@Task.register("data_source:db")
class DBDataSource(BaseDataSource):

    @classmethod
    def handle_exact_match(cls, folder_path, reverse_d):
        filepaths = {}
        for fp in Path(folder_path).rglob('*'):
            if fp.name in reverse_d:
                filepaths[reverse_d[fp.name]] = str(fp)
        return filepaths

    @classmethod
    def handle_msprof_pattern(cls, folder_path, alias, filepaths):
        regex_pattern = r'^msprof_\d+\.json$'
        matched_files = []
        for fp in Path(folder_path).parent.rglob('*.json'):
            if re.match(regex_pattern, fp.name):
                matched_files.append(str(fp))
        if matched_files:
            if alias not in filepaths:
                filepaths[alias] = []
            filepaths[alias].extend(matched_files)
        return filepaths

    @classmethod
    def handle_other_wildcard_patterns(cls, folder_path, pattern, alias, filepaths):
        for fp in Path(folder_path).rglob(pattern):
            filepaths[alias] = str(fp)
            break
        return filepaths

    @classmethod
    def handle_service_pattern(cls, folder_path, alias, filepaths):
        regex_pattern = r'^ms_service_[\w.-]+.db'
        matched_files = []
        for fp in Path(folder_path).rglob('*.db'):
            if re.match(regex_pattern, fp.name):
                matched_files.append(str(fp))
        if matched_files:
            if alias not in filepaths:
                filepaths[alias] = []
            filepaths[alias].extend(matched_files)
        return filepaths

    @classmethod
    def get_filepaths(cls, folder_path, file_filter):
        filepaths = {}
        reverse_d = {value: key for key, value in file_filter.items()}
        wildcard_patterns = [p for p in reverse_d.keys() if "*" in p or "?" in p]

        # 精确匹配的文件路径
        filepaths = cls.handle_exact_match(folder_path, reverse_d)

        # 创建映射
        pattern_handlers = {
            "msprof_*.json": cls.handle_msprof_pattern,
            "ms_service_*.db": cls.handle_service_pattern
        }

        # 通配符匹配的文件路径
        for pattern in wildcard_patterns:
            alias = reverse_d[pattern]
            handler = pattern_handlers.get(pattern, cls.handle_other_wildcard_patterns)
            filepaths = handler(folder_path, alias, filepaths)

        return filepaths

    @classmethod
    def get_prof_paths(cls, input_path: str):
        file_filter = {
            "service": "ms_service_*.db"
        }

        filepaths = cls.get_filepaths(input_path, file_filter)

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

