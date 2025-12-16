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

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from ms_service_profiler.exporters.exporter_coordinator import ExporterCoordinator


@pytest.fixture(autouse=True)
def reset_singleton():
    ExporterCoordinator.args = None


class TestExporterCoordinator:
    @patch("ms_service_profiler.exporters.exporter_coordinator.write_result_to_db")
    @patch("ms_service_profiler.exporters.exporter_coordinator.write_result_to_csv")
    def test_full_flow(self, mock_csv, mock_db):
        raw = pd.DataFrame(
            [
                {
                    "domain": "Coordinator",
                    "start_datetime": "2025-08-14 16:00:00:000000",
                    "message": {
                        "name": "RequestDispatch",
                        "rid": "req-1",
                        "PrefillAddress": "P-1",
                        "DecodeAddress": "D-1",
                    },
                },
                {
                    "domain": "Coordinator",
                    "start_datetime": "2025-08-14 16:00:05:000000",
                    "message": {"name": "GenerateToken", "Phase": "prefill", "rid": "req-1"},
                },
                {
                    "domain": "Coordinator",
                    "start_datetime": "2025-08-14 16:00:10:000000",
                    "message": {"name": "ReqFinish", "rid": "req-1"},
                },
            ]
        )

        args = MagicMock()
        args.format = ["db", "csv"]
        args.output_path = "/tmp"
        ExporterCoordinator.initialize(args)

        ExporterCoordinator.export({"tx_data_df": raw})

        assert mock_db.called
        assert mock_csv.called