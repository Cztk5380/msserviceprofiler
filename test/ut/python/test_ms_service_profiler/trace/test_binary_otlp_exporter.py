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

import os
import pytest
from unittest.mock import MagicMock, patch
from ms_service_profiler.tracer.binary_otlp_exporter import (
    BinaryOTLPSpanExporter, create_exporter_from_env, check_export_initialization, export_binary_data)


class TestBinaryOTLPSpanExporter:
    def test_init_grpc_exporter(self):
        """Test initializing GRPC exporter"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.GRPCBinaryExporter') as mock_grpc_exporter:
            exporter = BinaryOTLPSpanExporter(endpoint="http://test-endpoint:port", protocol="grpc")
            assert exporter.protocol == "grpc"
            mock_grpc_exporter.assert_called_once_with("http://test-endpoint:port")

    def test_init_http_exporter(self):
        """Test initializing HTTP exporter"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.HTTPBinaryExporter') as mock_http_exporter:
            exporter = BinaryOTLPSpanExporter(endpoint="http://test-endpoint:port/v1/traces", protocol="http/protobuf")
            assert exporter.protocol == "http/protobuf"
            mock_http_exporter.assert_called_once_with("http://test-endpoint:port/v1/traces")

    def test_init_exporter_failure(self):
        """Test exporter initialization failure scenario"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.GRPCBinaryExporter',
                   side_effect=Exception("Init error")):
            exporter = BinaryOTLPSpanExporter(endpoint="test-endpoint")
            assert exporter.exporter is None

    def test_is_initialized(self):
        """Test is_initialized method"""
        # Scenario 1: initialized
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.GRPCBinaryExporter'):
            exporter = BinaryOTLPSpanExporter(endpoint="test-endpoint")
            assert exporter.is_initialized() is True
        # Scenario 2: not initialized
        exporter = BinaryOTLPSpanExporter(endpoint="test-endpoint")
        exporter.exporter = None
        assert exporter.is_initialized() is False

    def test_export_success(self):
        """Test export success scenario"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.GRPCBinaryExporter') as mock_grpc_exporter:
            # Mock exporter.export returning SUCCESS
            mock_export = MagicMock(return_value=0)
            mock_grpc_exporter.return_value.export = mock_export
            exporter = BinaryOTLPSpanExporter(endpoint="test-endpoint")
            result = exporter.export(b"test-data")
            mock_export.assert_called_once_with(b"test-data")
            assert result is True

    def test_export_failure(self):
        """Test export failure scenario"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.GRPCBinaryExporter') as mock_grpc_exporter:
            # Mock exporter.export returning FAILED
            mock_export = MagicMock(return_value=1)
            mock_grpc_exporter.return_value.export = mock_export
            exporter = BinaryOTLPSpanExporter(endpoint="test-endpoint")
            result = exporter.export(b"test-data")
            assert result is False

    def test_export_invalid_data(self):
        """Test exporting invalid data scenario"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.GRPCBinaryExporter'):
            exporter = BinaryOTLPSpanExporter(endpoint="test-endpoint")
            # Scenario 1: None data
            result = exporter.export(None)
            assert result is False
            # Scenario 2: non-bytes/bytearray data
            result = exporter.export("invalid-data")
            assert result is False

    def test_export_not_initialized(self):
        """Test exporting when not initialized"""
        exporter = BinaryOTLPSpanExporter(endpoint="test-endpoint")
        exporter.exporter = None
        result = exporter.export(b"test-data")
        assert result is False


class TestGlobalFunctions:
    @pytest.fixture(autouse=True)
    def reset_global_exporter(self):
        """Reset global exporter after each test case"""
        yield
        from ms_service_profiler.tracer import binary_otlp_exporter
        binary_otlp_exporter._global_exporter = None

    def test_create_exporter_from_env_singleton(self):
        """Test create_exporter_from_env singleton behavior"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.BinaryOTLPSpanExporter') as mock_exporter_cls:
            with patch.dict(os.environ, {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://test-endpoint:1000",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc"
            }):
                # First creation
                exporter1 = create_exporter_from_env()
                # Second creation (reuse singleton)
                exporter2 = create_exporter_from_env()
                assert exporter1 is exporter2
                mock_exporter_cls.assert_called_once_with("http://test-endpoint:1000", "grpc")

    def test_create_exporter_no_endpoint(self):
        """Test creating exporter without endpoint"""
        with patch.dict(os.environ, {}, clear=True):
            exporter = create_exporter_from_env()
            assert exporter is None

    def test_create_exporter_endpoint_no_port(self):
        """Test creating exporter without port in endpoint"""
        with patch.dict(os.environ, {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://test-endpoint",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc"
        }):
            exporter = create_exporter_from_env()
            assert exporter is None

    def test_create_exporter_endpoint_error_scheme(self):
        """Test creating exporter without correct scheme in endpoint"""
        with patch.dict(os.environ, {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "httpss://test-endpoint",
        }):
            exporter = create_exporter_from_env()
            assert exporter is None

    def test_create_exporter_endpoint_error_protocol(self):
        """Test creating exporter without correct protocol in endpoint"""
        with patch.dict(os.environ, {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "httpss://test-endpoint",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpcs"
        }):
            exporter = create_exporter_from_env()
            assert exporter is None

    def test_create_exporter_exception(self):
        """Test creating exporter with exception"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.BinaryOTLPSpanExporter',
                   side_effect=Exception("Create error")):
            with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "test-endpoint"}):
                exporter = create_exporter_from_env()
                assert exporter is None

    def test_create_exporter_with_unsupported_tls_config(self):
        """Test creating exporter with tls config failure unsupported env"""
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE": "/client/cert"}):
            exporter = create_exporter_from_env()
            assert exporter is None

    def test_create_exporter_with_tls_config_missing_cert(self):
        """Test creating exporter with tls config failure missing cert"""
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_CERTIFICATE": "/ca/cert"}):
            exporter = create_exporter_from_env()
            assert exporter is None

    def test_check_export_initialization_success(self):
        """Test check_export_initialization success"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.BinaryOTLPSpanExporter') as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.is_initialized.return_value = True
            mock_exporter_cls.return_value = mock_exporter
            with patch.dict(os.environ, {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://test-endpoint:1000",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc"
            }):
                result = check_export_initialization()
                assert result is True

    def test_check_export_initialization_failure(self):
        """Test check_export_initialization failure"""
        with patch.dict(os.environ, {}, clear=True):
            result = check_export_initialization()
            assert result is False

    def test_export_binary_data_success(self):
        """Test export_binary_data success"""
        with patch('ms_service_profiler.tracer.binary_otlp_exporter.BinaryOTLPSpanExporter') as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.export.return_value = True
            mock_exporter_cls.return_value = mock_exporter
            with patch.dict(os.environ, {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://test-endpoint:1000",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc"
            }):
                result = export_binary_data(b"test-data")
                assert result is True

    def test_export_binary_data_failure(self):
        """Test export_binary_data failure"""
        with patch.dict(os.environ, {}, clear=True):
            result = export_binary_data(b"test-data")
            assert result is False