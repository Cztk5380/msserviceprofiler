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

import argparse
from importlib.metadata import entry_points


def _load_entries():
    eps = entry_points()
    ep_group = 'ms_service_profiler_plugins'
    plugin_eps = eps.select(group=ep_group)

    yield from (ep.load() for ep in plugin_eps)


def main():  
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="[MindStudio] msserviceprofiler command line tool"
    )
    subparsers = parser.add_subparsers(help="sub-command help")

    for entry_fn in _load_entries():
        entry_fn(subparsers)

    args = parser.parse_args()

    # run
    if hasattr(args, "func"):
        args.func(args=args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
