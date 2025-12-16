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

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock

import argparse
import pytest

from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.exporters.exporter_batch import ExporterBatchData
from ms_service_profiler.utils.log import set_logger
from ms_service_profiler.ms_service_profiler_ext import analyze
from ms_service_profiler.ms_service_profiler_ext.analyze import add_summary_exporter, main, arg_parse
from ms_service_profiler.ms_service_profiler_ext.exporters.exporter_summary import ExporterSummary


class TestMainFunction:
    mock_args = None
    mocker = None

    @property
    def mock_args(self):
        return self.__class__.mock_args

    @mock_args.setter
    def mock_args(self, value):
        self.__class__.mock_args = value

    @property
    def mocker(self):
        return self.__class__.mocker

    @mocker.setter
    def mocker(self, value):
        self.__class__.mocker = value

    def test_add_summary_exporter_decorator(self):
        mock_initialize = self.mocker.patch.object(ExporterSummary, "initialize")
        original_create_exporters = MagicMock(return_value=["exporter1", "exporter2"])

        wrapped_func = add_summary_exporter(original_create_exporters)

        args = Namespace(output_path="/fake/output")
        exporters = wrapped_func(args)

        assert len(exporters) == 3
        assert isinstance(exporters[0], ExporterSummary)
        mock_initialize.assert_called_once_with(args)

    def test_command_line_interface(self):
        mock_main = self.mocker.patch("ms_service_profiler.ms_service_profiler_ext.analyze.main")
        self.mocker.patch("sys.argv", ["script_name", "analyze", "--input-path", "/fake/input"])

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='command')
        arg_parse(subparsers)
        main(parser.parse_args())

    def test_invalid_input_path(self):
        self.mocker.patch("argparse.ArgumentParser.parse_args", side_effect=ValueError("Invalid path: '/invalid/path'"))

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='command')
        arg_parse(subparsers)
        with pytest.raises(ValueError, match=r"Invalid path.*"):
            main(parser.parse_args())

    def test_main_applies_summary_exporter_decorator(self):
        original_exporters = [ExporterBatchData]
        self.mocker.patch(
            "ms_service_profiler.exporters.factory.ExporterFactory.create_exporters", return_value=original_exporters
        )

        spy_add_summary = self.mocker.spy(analyze, "add_summary_exporter")

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='command')
        arg_parse(subparsers)
        main(parser.parse_args())

        spy_add_summary.assert_called_once_with(ExporterFactory.create_exporters)

        wrapped_create_exporters = spy_add_summary.spy_return
        exporters = wrapped_create_exporters(self.mock_args)
        assert len(exporters) == len(original_exporters) + 1
        assert isinstance(exporters[0], ExporterSummary)

    @pytest.fixture(autouse=True)
    def _inject_mocker(self, mocker):
        self.mocker = mocker
        self.mock_args = Namespace(input_path="/fake/input", output_path="/fake/output", log_level="info", format="csv")

        # 2. 配置全局mock
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=self.mock_args)
        mocker.patch("ms_service_profiler.utils.log.set_log_level")
        mocker.patch("ms_service_profiler.exporters.factory.ExporterFactory.create_exporters", return_value=[])
        mocker.patch.object(Path, "mkdir")
        mocker.patch("ms_service_profiler.exporters.utils.create_sqlite_db")
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.makedirs")
        mocker.patch("sqlite3.connect")

        yield
        self.mocker = None
        self.mock_args = None
