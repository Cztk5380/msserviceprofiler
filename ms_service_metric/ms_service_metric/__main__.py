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
"""
ms_service_metric 命令行入口

提供控制metric收集的命令行工具。

用法:
    python -m ms_service_metric on      # 开启metric收集
    python -m ms_service_metric off     # 关闭metric收集
    python -m ms_service_metric restart # 重启metric收集
    python -m ms_service_metric status  # 查看状态
"""

import sys

from ms_service_metric.control.cli import main

if __name__ == "__main__":
    sys.exit(main())
