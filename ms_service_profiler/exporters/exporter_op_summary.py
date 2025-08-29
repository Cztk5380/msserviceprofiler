import os
import shutil
import glob
import logging
from argparse import Namespace
from typing import Dict, Optional

from ms_service_profiler.exporters.base import ExporterBase

logger = logging.getLogger(__name__)

class ExporterOpSummaryCopier(ExporterBase):
    """操作摘要文件复制器"""
    
    name = "op_summary_copier"
    description = "Copy op_summary/op_statistic CSV files between PROF directories"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, source_root, target_root) -> None:
        """
        执行复制操作
        :param data: 依赖数据（本导出器不使用）
        """
        try:
            # 查找所有PROF目录
            prof_dirs = glob.glob(os.path.join(source_root, "PROF_*"))
            if not prof_dirs:
                logger.warning(f"在目录 {source_root} 下未找到任何PROF_*目录")
                return

            for prof_dir in prof_dirs:
                if not os.path.isdir(prof_dir):
                    continue

                prof_name = os.path.basename(prof_dir)
                source_dir = os.path.join(prof_dir, "mindstudio_profiler_output")
                target_dir = os.path.join(target_root, prof_name)

                if not os.path.exists(source_dir):
                    logger.warning(f"跳过 {prof_name}: 缺少mindstudio_profiler_output目录")
                    continue

                # 执行文件复制
                cls._copy_files(source_dir, target_dir)

        except Exception as e:
            logger.error(f"操作异常终止: {str(e)}", exc_info=True)
            raise  # 抛出异常，由上层处理

    @classmethod
    def _copy_files(cls, source_dir: str, target_dir: str):
        """执行单个PROF目录的文件复制"""
        os.makedirs(target_dir, exist_ok=True)
        copied_count = 0

        for pattern in ["op_summary*.csv", "op_statistic*.csv"]:
            for src_path in glob.glob(os.path.join(source_dir, pattern)):
                if os.path.isfile(src_path):
                    dest_path = os.path.join(target_dir, os.path.basename(src_path))
                    try:
                        shutil.copy2(src_path, dest_path)
                        copied_count += 1
                        logger.debug(f"已复制: {os.path.basename(src_path)}")
                    except Exception as e:
                        logger.error(f"复制失败: {src_path} -> {dest_path} | {str(e)}")