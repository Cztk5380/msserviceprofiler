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
MetricControlCLI - Metric控制命令行工具

提供命令行接口，用于控制目标进程中metric收集的开关。
通过共享内存和SIGUSR1信号与目标进程通信。

简化设计：
- 只需要start标志和时间戳
- start=False: 关闭metric收集
- start=True: 开启metric收集
- 时间戳变化表示需要重启（重新加载配置）

使用方式:
    ms-service-metric on      # 开启metric收集
    ms-service-metric off     # 关闭metric收集
    ms-service-metric restart # 重启metric收集（重新加载配置）
    ms-service-metric status  # 查看状态

环境变量:
    MS_SERVICE_METRIC_SHM_PREFIX - 共享内存和信号量名称前缀（默认: /ms_service_metric）
    MS_SERVICE_METRIC_MAX_PROCS  - 最大进程数（默认: 1000）
"""

import argparse
import os
import sys

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.utils.shm_manager import (
    DEFAULT_MAX_PROCS,
    DEFAULT_SHM_PREFIX,
    ENV_MAX_PROCS,
    ENV_SHM_PREFIX,
    SharedMemoryManager,
    POSIX_IPC_AVAILABLE,
)

logger = get_logger("cli")


def send_control_command(command: str, shm_prefix: str, max_procs: int) -> int:
    """发送控制命令
    
    命令逻辑：
    - on: 如果当前已经是ON，不做任何操作；否则改为ON并更新时间戳
    - off: 如果当前已经是OFF，不做任何操作；否则改为OFF并更新时间戳
    - restart: 直接改为ON（强制），更新时间戳，不判断当前状态
    
    对于off命令，如果执行后状态为OFF且没有进程，会释放共享内存。
    
    Args:
        command: 命令字符串（on/off/restart）
        shm_prefix: 共享内存前缀
        max_procs: 最大进程数
        
    Returns:
        退出码
    """
    try:
        manager = SharedMemoryManager(shm_prefix=shm_prefix, max_procs=max_procs)

        # 命令映射: 每个命令对应一个字典，明确指定参数含义
        command_map = {
            "on": {"is_start": True, "force": False, "create": True},
            "off": {"is_start": False, "force": False, "create": False},
            "restart": {"is_start": True, "force": True, "create": True},
        }
        cmd_config = command_map[command.lower()]
        is_start = cmd_config["is_start"]
        force = cmd_config["force"]
        create = cmd_config["create"]

        # 连接共享内存
        if not manager.connect(create=create):
            if command.lower() == "off":
                logger.info("No shared memory found, metric collection is already OFF")
                return 0
            logger.error("Failed to connect to shared memory")
            return 1
        
        # 发送命令
        success, signaled, cleaned, changed = manager.send_control_command(
            is_start=is_start,
            force=force,
            send_signal=True
        )
        
        if not success:
            logger.error("Failed to send command")
            return 1
        
        # 输出结果
        cmd_display = command.upper()
        if changed:
            msg = f"Metric collection {cmd_display}: {signaled} processes affected"
            if cleaned > 0:
                msg += f", {cleaned} invalid processes cleaned"
            logger.info(msg)
        else:
            state_str = "ON" if is_start else "OFF"
            logger.info(f"Metric collection already {state_str}, no change needed")
        
        # 对于off命令，检查是否需要释放共享内存
        if command.lower() == "off":
            if manager.should_destroy():
                logger.info("No active processes, releasing shared memory resources")
                manager.destroy()
                logger.info("Shared memory resources released")
        
        return 0
        
    except Exception as e:
        logger.error(f"{e}")
        return 1


def show_status(shm_prefix: str, max_procs: int) -> int:
    """显示状态
    
    同时会清理无效的进程，并在状态为OFF且没有进程时释放共享内存。
    
    Args:
        shm_prefix: 共享内存前缀
        max_procs: 最大进程数
        
    Returns:
        退出码
    """
    MAX_DISPLAY_PROCESSES = 10
    
    try:
        manager = SharedMemoryManager(shm_prefix=shm_prefix, max_procs=max_procs)
        
        if not manager.connect(create=False):
            # 共享内存不存在，说明没有进程在运行，状态为OFF，这是正常现象
            logger.info("Shared Memory Status:")
            logger.info("  State:            OFF")
            logger.info("  Timestamp:        0")
            logger.info("  Process Cursor:   0")
            logger.info("  Process List Len: 0")
            logger.info("  Process Count:    0")
            logger.info("  Note:             No shared memory found, no processes running")
            return 0

        status = manager.get_status()

        logger.info("Shared Memory Status:")
        logger.info(f"  State:            {status['state']}")
        logger.info(f"  Timestamp:        {status['timestamp']}")
        logger.info(f"  Process Cursor:   {status['process_cursor']}")
        logger.info(f"  Process List Len: {status['process_list_len']}")
        logger.info(f"  Process Count:    {status['process_count']}")

        if status['processes']:
            proc_msg = f"  Processes:        {', '.join(map(str, status['processes'][:MAX_DISPLAY_PROCESSES]))}"
            if len(status['processes']) > MAX_DISPLAY_PROCESSES:
                proc_msg += f" ... and {len(status['processes']) - MAX_DISPLAY_PROCESSES} more"
            logger.info(proc_msg)
        
        if status['cleaned'] > 0:
            logger.info(f"  Cleaned:          {status['cleaned']} invalid processes")
        
        if status['version_mismatch']:
            logger.warning("  Version:          MISMATCH (using default values)")
        
        # 检查是否需要释放共享内存
        if manager.should_destroy():
            logger.info("State is OFF and no active processes, releasing shared memory resources")
            manager.destroy()
            logger.info("Shared memory resources released")
        
        return 0
        
    except Exception as e:
        logger.error(f"{e}")
        return 1


def main() -> int:
    """主入口函数"""
    parser = argparse.ArgumentParser(
        prog="ms-service-metric",
        description="Control ms_service_metric collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  MS_SERVICE_METRIC_SHM_PREFIX  Shared memory and semaphore name prefix (default: /ms_service_metric)
  MS_SERVICE_METRIC_MAX_PROCS   Maximum number of processes (default: 1000)

Examples:
  ms-service-metric on
  ms-service-metric off
  ms-service-metric restart
  ms-service-metric status
        """
    )
    
    # 位置参数：命令
    parser.add_argument(
        "command",
        choices=["on", "off", "restart", "status"],
        help="Control command: on/off/restart/status"
    )
    
    # 可选参数
    parser.add_argument(
        "--shm-prefix",
        default=os.getenv(ENV_SHM_PREFIX, DEFAULT_SHM_PREFIX),
        help="Shared memory and semaphore name prefix (overrides environment variable)"
    )
    parser.add_argument(
        "--max-procs",
        type=int,
        default=int(os.getenv(ENV_MAX_PROCS, DEFAULT_MAX_PROCS)),
        help="Maximum number of processes (overrides environment variable)"
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # 检查posix_ipc是否可用
    if not POSIX_IPC_AVAILABLE:
        logger.error("posix_ipc module is required but not installed")
        logger.info("Install with: pip install posix_ipc")
        return 1
    
    # 执行命令
    if args.command == "status":
        return show_status(args.shm_prefix, args.max_procs)
    else:
        return send_control_command(args.command, args.shm_prefix, args.max_procs)


if __name__ == "__main__":
    sys.exit(main())
