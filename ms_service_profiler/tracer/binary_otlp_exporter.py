# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os
import threading
from typing import Optional, Union
from ms_service_profiler.utils.log import logger
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCExporter
from opentelemetry.sdk.trace.export import SpanExportResult


# Global exporter instance and lock
_global_exporter: Optional["BinaryOTLPSpanExporter"] = None
_exporter_lock = threading.Lock()


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
        self.endpoint = self._normalize_endpoint(endpoint, protocol)
        self.protocol = self._infer_protocol(endpoint, protocol)
        self.exporter = self._init_exporter(*args, **kwargs)


    @staticmethod
    def _normalize_endpoint(endpoint: str, protocol: Optional[str]) -> str:
        """Normalize endpoint URL by adding HTTP prefix if needed."""
        if protocol == "http/protobuf" and not endpoint.startswith(("http://", "https://")):
            return f"http://{endpoint}"
        return endpoint

    @staticmethod
    def _infer_protocol(endpoint: str, protocol: Optional[str]) -> str:
        """Infer communication protocol based on endpoint and protocol."""
        if protocol in ("grpc", "http/protobuf"):
            return protocol

        if endpoint.startswith(("http://", "https://")):
            return "http/protobuf"

        return "grpc"

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
    global _global_exporter

    with _exporter_lock:
        if _global_exporter is not None:
            return _global_exporter

        protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL")
        traces_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        global_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        endpoint = traces_endpoint or global_endpoint

        if not endpoint:
            logger.warning(
                "No endpoint configured - set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT or OTEL_EXPORTER_OTLP_ENDPOINT.")
            return None

        try:
            _global_exporter = BinaryOTLPSpanExporter(endpoint, protocol)
            logger.info(f"Start {protocol} exporter, endpoint: {endpoint}")
            return _global_exporter
        except Exception as e:
            logger.warning(f"Failed to create exporter: {str(e)}")
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
        logger.warning("Export aborted - no exporter available.")
        return False
    return exporter.export(data)
