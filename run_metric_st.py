# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import os
import sys


def main() -> int:
    st_python_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test", "st", "python")
    if st_python_dir not in sys.path:
        sys.path.insert(0, st_python_dir)

    import importlib

    metric_entry = importlib.import_module("metric.run_metric_st")
    return metric_entry.main()


if __name__ == "__main__":
    raise SystemExit(main())
