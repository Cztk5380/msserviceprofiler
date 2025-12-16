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


from .base import BaseComparator


class DBComparator(BaseComparator):
    SUPPORTED_EXTENSIONS = ['.db']

    def process(self, file_a, file_b):
        cursor = self.out_db_conn.cursor()
        cursor.execute(f"ATTACH '{file_a}' AS src1")
        cursor.execute(f"ATTACH '{file_b}' AS src2")

        self._merge_tables(cursor, 'modelExec')
        self._merge_tables(cursor, 'BatchSchedule')
        self.out_db_conn.commit()

    def _merge_tables(self, cursor, table_name):
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                batch_type TEXT,
                batch_size_a INTEGER,
                batch_size_b INTEGER
            )
        ''')

        cursor.execute(f'''
            INSERT INTO {table_name}
            SELECT
                src1.batch.batch_type,
                src1.batch.batch_size,
                src2.batch.batch_size
            FROM src1.batch
            INNER JOIN src2.batch
                ON src1.batch.name = src2.batch.name
                AND src1.batch.name = '{table_name}'
        ''')
