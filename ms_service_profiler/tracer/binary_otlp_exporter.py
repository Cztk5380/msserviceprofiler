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
import stat
import threading
from typing import Optional, Union
from urllib.parse import urlparse

from ms_service_profiler.utils.log import logger
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCExporter
from opentelemetry.sdk.trace.export import SpanExportResult


# Global exporter instance and lock
_global_exporter: Optional["BinaryOTLPSpanExporter"] = None
_exporter_lock = threading.Lock()
PROTOCOLS = ("http/protobuf", "grpc")
SCHEME = ("http", "https")


class GRPCBinaryExporter(GRPCExporter):
    """GRPC-based binary exporter."""
    def __init__(self, endpoint: str, *args, **kwargs):
        super().__init__(endpoint=endpoint, *args, **kwargs)

    def _translate_data(self, data: ExportTraceServiceRequest) -> ExportTraceServiceRequest:
        """Translate data for export."""
        return data

    def export(self, binary_data: bytes) -> SpanExportResult:
        """Export binary data using GRPC."""
        try:
            export_request = ExportTraceServiceRequest()
            export_request.ParseFromString(binary_data)
            return super().export(export_request)
        except Exception as e:
            raise e


class HTTPBinaryExporter(HTTPExporter):
    """HTTP-based binary exporter."""
    def __init__(self, endpoint: str, *args, **kwargs):
        super().__init__(endpoint, *args, **kwargs)

    def export(self, binary_data: bytes) -> SpanExportResult:
        """
        Export binary data using HTTP.
        The applicable version of opentelemetry-exporter-otlp-proto-http is <= 1.34.1.
        The recommended version is 1.33.1.
        """
        try:
            return self._export_serialized_spans(binary_data)
        except Exception as e:
            raise e


class BinaryOTLPSpanExporter:
    """Binary OTLP tracer data exporter supporting HTTP/protobuf and gRPC protocols."""
    def __init__(self,
                 endpoint: Optional[str] = None,
                 protocol: Optional[str] = None,
                 *args, **kwargs):
        """Initialize the binary OTLP exporter."""
        self.endpoint = endpoint
        self.protocol = protocol
        self.exporter = self._init_exporter(*args, **kwargs)

    def _init_exporter(self, *args, **kwargs):
        """Initialize appropriate exporter based on protocol."""
        try:
            if self.protocol == "http/protobuf":
                return HTTPBinaryExporter(self.endpoint, *args, **kwargs)
            else:
                return GRPCBinaryExporter(self.endpoint, *args, **kwargs)
        except Exception as e:
            logger.warning(f"Exporter initialization failed: {str(e)}.")
            return None

    def is_initialized(self) -> bool:
        """Check if exporter is successfully initialized."""
        return hasattr(self, "exporter") and self.exporter is not None

    def export(self, export_data: Union[bytearray, bytes]) -> bool:
        """Export tracer data to OTLP receiver."""
        if not self.is_initialized():
            return False

        if not export_data or not isinstance(export_data, (bytearray, bytes)):
            logger.warning(f"Unsupported data type: {type(export_data)}.")
            return False

        try:
            result = self.exporter.export(export_data)
            success = result == SpanExportResult.SUCCESS
            status = "successfully" if success else "failed"
            if not success:
                logger.warning(f"Export tracer via {self.protocol} {status}")
            logger.debug(f"Export tracer via {self.protocol} {status}")
            return success
        except Exception as e:
            logger.warning(f"Export tracer error: {str(e)}")
            return False


def create_exporter_from_env() -> Union[BinaryOTLPSpanExporter, None]:
    """Create exporter instance using OpenTelemetry environment variables."""

    def _validation_endpoint(url: str) -> bool:
        try:
            parsed = urlparse(url)
            port = parsed.port
            if parsed.scheme not in SCHEME:
                logger.warning("Unexpected endpoint scheme (choose from 'http', 'https')")
                return False
            if not port or not isinstance(port, int):
                logger.warning("Unexpected endpoint port (0 < port <= 65535)")
                return False
        except Exception as e:
            logger.warning(f"Unexpected endpoint: {e}")
            return False
        return True

    def _get_endpoint_and_protocol_from_env():
        protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL")
        if not protocol or protocol not in PROTOCOLS:
            raise Exception("No correct protocol configuration found, "
                            "need check OTEL_EXPORTER_OTLP_PROTOCOL (choose from 'http/protobuf', 'grpc')")

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint or not _validation_endpoint(endpoint):
            raise Exception("No correct endpoint configuration found, need check OTEL_EXPORTER_OTLP_ENDPOINT.")
        return endpoint, protocol

    def _check_tls_config_from_env():
        client_key_file = (os.environ.get("OTEL_EXPORTER_OTLP_TRACES_CLIENT_KEY") or
                           os.environ.get("OTEL_EXPORTER_OTLP_CLIENT_KEY"))
        client_certificate_file = (os.environ.get("OTEL_EXPORTER_OTLP_TRACES_CLIENT_CERTIFICATE") or
                                   os.environ.get("OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE"))
        if client_key_file or client_certificate_file:
            raise Exception("TLS client configuration found (OTEL_EXPORTER_OTLP_TRACES_CLIENT_KEY/"
                           "OTEL_EXPORTER_OTLP_CLIENT_KEY/OTEL_EXPORTER_OTLP_TRACES_CLIENT_CERTIFICATE/"
                           "OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE), but mTLS communication is not supported.")

        certificate_file = os.environ.get("OTEL_EXPORTER_OTLP_CERTIFICATE")
        if certificate_file:
            if not os.path.exists(certificate_file) or not os.path.isfile(certificate_file):
                raise Exception(f"No correct certificate configuration found, need check OTEL_EXPORTER_OTLP_CERTIFICATE.")

            cert_dir = os.path.dirname(certificate_file)
            if not cert_dir:
                cert_dir = os.getcwd()

            dir_stat = os.stat(cert_dir)
            dir_mode = stat.S_IMODE(dir_stat.st_mode)
            file_stat = os.stat(certificate_file)
            file_mode = stat.S_IMODE(file_stat.st_mode)
            if (dir_mode != 0o700 or dir_stat.st_uid != os.getuid() or
                    file_mode != 0o600 or file_stat.st_uid != os.getuid()):
                raise PermissionError("No correct certificate file found: "
                                      "The permission on the directory of certificate must be 700, "
                                      "the permission on the certificate must be 600, "
                                      "and the owner must be the same as that of the current user, "
                                      "need check OTEL_EXPORTER_OTLP_CERTIFICATE.")


    global _global_exporter

    with _exporter_lock:
        if _global_exporter is not None:
            return _global_exporter

        try:
            _check_tls_config_from_env()
            endpoint, protocol = _get_endpoint_and_protocol_from_env()
            _global_exporter = BinaryOTLPSpanExporter(endpoint, protocol)
            logger.info(f"Start {protocol} exporter, endpoint: {endpoint}")
            return _global_exporter
        except Exception as e:
            logger.error(f"Failed to create exporter: {str(e)}")
            _global_exporter = None
            return None


def check_export_initialization() -> bool:
    """Check if the exporter is initialized."""
    exporter = create_exporter_from_env()
    if exporter is None:
        return False
    return exporter.is_initialized()


def export_binary_data(data: Union[bytearray, bytes]) -> bool:
    """Convenience function to export binary data."""
    exporter = create_exporter_from_env()
    if not exporter:
        logger.warning("Export aborted, no exporter available.")
        return False
    return exporter.export(data)