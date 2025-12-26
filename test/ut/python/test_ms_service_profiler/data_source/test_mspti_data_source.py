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

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
from ms_service_profiler.data_source.mspti_data_source import MsptiDataSource
from ms_service_profiler.utils.error import LoadDataError


@patch('sqlite3.connect')
def test_load_ops_db(mock_connect):
    # Mock the connection and cursor
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Mock the read_sql_query method
    with patch('pandas.read_sql_query') as mock_read_sql_query:
        mock_read_sql_query.return_value = pd.DataFrame()

        # Call the method
        result = MsptiDataSource.load_ops_db('dummy_path', 'dummy_id')

        # Assert that the read_sql_query method was called twice
        assert mock_read_sql_query.call_count == 3

        # Assert that the result is a tuple of two DataFrames
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], pd.DataFrame)
        assert isinstance(result[1], pd.DataFrame)
        assert isinstance(result[2], pd.DataFrame)


@patch('pathlib.Path.rglob')
def test_get_prof_paths(mock_rglob):
    # Mock the rglob method
    mock_path = MagicMock()
    mock_path.is_file.return_value = True
    mock_path.name = 'ascend_service_profiler_test-0.db'
    mock_path_not_file = MagicMock()
    mock_path_not_file.is_file.return_value = False
    mock_path_not_file.name = 'ascend_service_profiler_test-0.db'
    mock_path_bad_name = MagicMock()
    mock_path_bad_name.is_file.return_value = True
    mock_path_bad_name.name = 'bad_ascend_service_profiler_test-0.db'
    mock_rglob.return_value = [mock_path, mock_path_not_file, mock_path_bad_name]

    # Call the method
    result = MsptiDataSource.get_prof_paths('dummy_path')

    # Assert that the result is a list of tuples
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], tuple)
    assert len(result[0]) == 2


@patch('ms_service_profiler.data_source.mspti_data_source.MsptiDataSource.load_ops_db')
def test_load(mock_load_ops_db):
    # Mock the load_ops_db method
    mock_load_ops_db.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    # Call the method
    result = MsptiDataSource(None).load(('dummy_path', 'dummy_id'))

    # Assert that the result is a dictionary
    assert isinstance(result, dict)
    assert 'api_df' in result
    assert 'kernel_df' in result
    assert 'db_id' in result

    # Test exception handling
    mock_load_ops_db.side_effect = Exception('Test exception')
    with pytest.raises(LoadDataError):
        MsptiDataSource(None).load(('dummy_path', 'dummy_id'))