# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os
import shutil
import glob
from pathlib import Path  # 添加Path导入

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger


class ExporterOpSummaryCopier(ExporterBase):
    """Operation summary file copier"""
    
    name = "op_summary_copier"
    description = "Copy op_summary/op_statistic CSV files between PROF directories"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        """
        Execute copy operation
        :param data: Dependency data (not used by this exporter)
        """
        source_root = cls.args.input_path
        target_root = cls.args.output_path
        try:
            prof_dirs = []
            for path in Path(source_root).glob("**/PROF_*"):
                if path.is_dir():
                    prof_dirs.append(str(path))
                    
            if not prof_dirs:
                return

            for prof_dir in prof_dirs:
                prof_name = os.path.basename(prof_dir)
                source_dir = os.path.join(prof_dir, "mindstudio_profiler_output")
                target_dir = os.path.join(target_root, prof_name)

                if not os.path.exists(source_dir):
                    continue

                # 检查op_summary文件
                op_summary_files = glob.glob(os.path.join(source_dir, "op_summary*.csv"))
                if not op_summary_files:
                    continue

                # 执行文件复制
                copied_count = cls._copy_files(source_dir, target_dir)
                if copied_count > 0:
                    logger.debug(f"copy folder: {prof_name}")

        except (IOError, OSError) as e:
            logger.error(f"Failed to copy files from {source_root}: {e}", exc_info=True)
            raise

    @classmethod
    def _copy_files(cls, source_dir: str, target_dir: str) -> int:
        """Perform file copy for single PROF directory"""
        os.makedirs(target_dir, exist_ok=True)
        copied_count = 0

        for pattern in ["op_summary*.csv", "op_statistic*.csv"]:
            for src_path in glob.glob(os.path.join(source_dir, pattern)):
                if os.path.isfile(src_path):
                    dest_path = os.path.join(target_dir, os.path.basename(src_path))
                    try:
                        shutil.copy2(src_path, dest_path)
                        copied_count += 1
                    except Exception as e:
                        logger.error(f"Copy failed: {src_path} -> {dest_path} | {str(e)}")

        return copied_count