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


from abc import ABC, abstractmethod


class BaseComparator(ABC):
    SUPPORTED_EXTENSIONS = []
    
    def __init__(self, out_db_conn, excel_writer):
        self.out_db_conn = out_db_conn
        self.excel_writer = excel_writer
    
    @classmethod
    def supports(cls, file_extension):
        return file_extension in cls.SUPPORTED_EXTENSIONS
    
    @abstractmethod
    def process(self, file_a, file_b):
        pass
