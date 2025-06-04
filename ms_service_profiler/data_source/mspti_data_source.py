# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import re
from pathlib import Path

import sqlite3
import pandas as pd

from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.error import LoadDataError


@Task.register("data_source:mspti")
class MsptiDataSource(BaseDataSource):
    @staticmethod
    def load_ops_db(filepath, db_id):
        with sqlite3.connect(filepath) as conn:
            api_query = """
            SELECT name, start, end, processId, threadId, correlationId FROM Api order by correlationId asc
            """
            kernel_query = """
            SELECT name, type, start, end, deviceId, streamId, correlationId FROM Kernel order by correlationId asc
            """
            communication_query = """
            SELECT name, start, end, deviceId, streamId, dataCount, dataType, commGroupName, correlationId FROM Communication 
            order by correlationId asc
            """
            api_df = pd.read_sql_query(api_query, conn)
            kernel_df = pd.read_sql_query(kernel_query, conn)
            communication_df = pd.read_sql_query(communication_query, conn)
            api_df["db_id"] = db_id
            kernel_df["db_id"] = db_id
            communication_df["db_id"] = db_id
        return api_df, kernel_df, communication_df

    @classmethod
    def get_prof_paths(cls, input_path: str):
        filepaths = []
        # 合并后的正则表达式，同时验证文件名格式和提取通配符内容
        unified_pattern = re.compile(r'^ascend_service_profiler_(.+)\.db$')

        for fp in Path(input_path).rglob('*'):  # 遍历所有文件
            match = unified_pattern.match(fp.name)
            if fp.is_file() and match:
                filepaths.append((str(fp), match.group(1)))
        return filepaths

    def load(self, prof_path):
        db_path, db_id = prof_path
        try:
            api_df, kernel_df, communication_df = self.load_ops_db(db_path, db_id)
            return dict(
                    api_df=api_df,
                    kernel_df=kernel_df,
                    communication_df=communication_df,
                    db_id=db_id
                )
        except Exception as ex:
            raise LoadDataError(db_path) from ex
