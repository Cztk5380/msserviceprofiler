# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os
import pytest
from unittest.mock import MagicMock

from ms_service_profiler.exporters.exporter_op_summary import ExporterOpSummaryCopier

@pytest.fixture
def setup_dirs(tmp_path):
    """创建测试用的源目录和目标目录"""
    source_root = os.path.join(tmp_path, "source")
    os.makedirs(source_root, exist_ok=True)
    target_root = os.path.join(tmp_path, "target")
    os.makedirs(target_root, exist_ok=True)
    return source_root, target_root

@pytest.fixture
def mock_args(setup_dirs):
    """创建模拟的args对象"""
    source, target = setup_dirs
    args = MagicMock()
    args.input_path = source
    args.output_path = target
    return args

def test_no_prof_directories(mock_args):
    """测试没有PROF目录的情况"""
    ExporterOpSummaryCopier.initialize(mock_args)
    ExporterOpSummaryCopier.export(None)
    assert len(os.listdir(mock_args.output_path)) == 0

def test_prof_dir_without_mindstudio_output(mock_args):
    """测试PROF目录中没有mindstudio_profiler_output的情况"""
    prof_dir = os.path.join(mock_args.input_path, "PROF_0")
    os.makedirs(prof_dir)
    
    ExporterOpSummaryCopier.initialize(mock_args)
    ExporterOpSummaryCopier.export(None)
    assert len(os.listdir(mock_args.output_path)) == 0

def test_mindstudio_output_without_op_summary(mock_args):
    """测试mindstudio_profiler_output中没有op_summary文件的情况"""
    prof_dir = os.path.join(mock_args.input_path, "PROF_0", "mindstudio_profiler_output")
    os.makedirs(prof_dir)
    with open(os.path.join(prof_dir, "other_file.txt"), "w") as f:
        f.write("test")
    
    ExporterOpSummaryCopier.initialize(mock_args)
    ExporterOpSummaryCopier.export(None)
    assert len(os.listdir(mock_args.output_path)) == 0

def test_successful_copy_single_prof_dir(mock_args):
    """测试成功复制单个PROF目录"""
    prof_dir = os.path.join(mock_args.input_path, "PROF_0", "mindstudio_profiler_output")
    os.makedirs(prof_dir)
    
    # 创建测试文件
    open(os.path.join(prof_dir, "op_summary_0.csv"), "a").close()
    open(os.path.join(prof_dir, "op_statistic_0.csv"), "a").close()
    open(os.path.join(prof_dir, "other_file.txt"), "a").close()

    ExporterOpSummaryCopier.initialize(mock_args)
    ExporterOpSummaryCopier.export(None)
    
    # 验证目标文件
    target_dir = os.path.join(mock_args.output_path, "PROF_0")
    assert os.path.isfile(os.path.join(target_dir, "op_summary_0.csv"))
    assert os.path.isfile(os.path.join(target_dir, "op_statistic_0.csv"))
    assert not os.path.exists(os.path.join(target_dir, "other_file.txt"))

def test_multiple_prof_directories(mock_args):
    """测试复制多个PROF目录"""
    # 创建3个PROF目录
    for i in range(3):
        prof_dir = os.path.join(mock_args.input_path, f"PROF_{i}", "mindstudio_profiler_output")
        os.makedirs(prof_dir)
        open(os.path.join(prof_dir, f"op_summary_{i}.csv"), "a").close()
        open(os.path.join(prof_dir, f"op_statistic_{i}.csv"), "a").close()

    ExporterOpSummaryCopier.initialize(mock_args)
    ExporterOpSummaryCopier.export(None)

    # 验证所有目录
    for i in range(3):
        target_dir = os.path.join(mock_args.output_path, f"PROF_{i}")
        assert os.path.isfile(os.path.join(target_dir, f"op_summary_{i}.csv"))
        assert os.path.isfile(os.path.join(target_dir, f"op_statistic_{i}.csv"))