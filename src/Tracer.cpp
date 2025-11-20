// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

#include <iostream>
#include <string>
#include <vector>
#include <array>
#include <limits>
#include <cstdint>
#include <random>
#include <mutex>
#include <new>

#include <google/protobuf/util/json_util.h>
#include "opentelemetry/proto/trace/v1/trace.pb.h"
#include "opentelemetry/proto/collector/trace/v1/trace_service.pb.h"

#include "msServiceProfiler/ServiceProfilerInterface.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceTracer.h"
#include "msServiceProfiler/Tracer.h"

#define TraceSpanHandle

static opentelemetry::proto::resource::v1::Resource gResourceProto_;
using SpanPtr = opentelemetry::proto::trace::v1::Span *;

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
opentelemetry::proto::resource::v1::Resource& getResourceProto()
{
    return gResourceProto_;
}
#endif

void ResAddAttr(const char *key, const char *value)
{
    if (key == nullptr || value == nullptr) {
        return;
    }
    auto attr = gResourceProto_.add_attributes();
    attr->set_key(key);
    attr->mutable_value()->set_string_value(value);
}

TRACE_SPAN_DATA NewSpanData(const char *spanName)
{
    if (spanName == nullptr) {
        return nullptr;
    }
    opentelemetry::proto::trace::v1::Span *spanPb = new(std::nothrow) opentelemetry::proto::trace::v1::Span();
    if (spanPb == nullptr) {
        return nullptr;
    }
    spanPb->set_name(spanName);
    spanPb->set_kind(opentelemetry::proto::trace::v1::Span_SpanKind_SPAN_KIND_SERVER);
    spanPb->set_flags(opentelemetry::proto::trace::v1::SPAN_FLAGS_CONTEXT_HAS_IS_REMOTE_MASK);
    spanPb->set_start_time_unix_nano(MsUtils::GetCurrentTimeInNanoseconds());
    return spanPb;
}

void SpanActivate(TRACE_SPAN_DATA spanData, uint64_t startTime)
{
    if (!spanData) {
        return;
    }
    SpanPtr spanPb = (SpanPtr)spanData;
    if (startTime == 0) {
        spanPb->set_start_time_unix_nano(MsUtils::GetCurrentTimeInNanoseconds());
    } else {
        spanPb->set_start_time_unix_nano(startTime);
    }
}

void SpanFillCtxData(TRACE_SPAN_DATA spanData, TraceId traceid, SpanId spanid, SpanId pSpanid)
{
    if (!spanData) {
        return;
    }
    SpanPtr spanPb = (SpanPtr)spanData;
    spanPb->set_trace_id(traceid.as_char.data(), sizeof(TraceId));
    spanPb->set_parent_span_id(pSpanid.as_char.data(), sizeof(SpanId));
    spanPb->set_span_id(spanid.as_char.data(), sizeof(SpanId));
}

void SpanAddAttribute(TRACE_SPAN_DATA spanData, const char *attrName, const char *value)
{
    if (!spanData || attrName == nullptr || value == nullptr) {
        return;
    }
    SpanPtr spanPb = (SpanPtr)spanData;
    auto attribute = spanPb->add_attributes();
    attribute->set_key(attrName);
    attribute->mutable_value()->set_string_value(value);
}

void SpanSetStatus(TRACE_SPAN_DATA spanData, const bool isSuccess, const std::string &msg)
{
    auto code = isSuccess ? opentelemetry::proto::trace::v1::Status::STATUS_CODE_OK
                          : opentelemetry::proto::trace::v1::Status::STATUS_CODE_ERROR;

    if (!spanData) {
        return;
    }
    SpanPtr spanPb = (SpanPtr)spanData;
    spanPb->mutable_status()->set_code(code);
    if (!isSuccess) {
        spanPb->mutable_status()->set_message(msg);
    }
}

void SpanEndAndFree(TRACE_SPAN_DATA spanData, std::string &&moduleName_)
{
    if (!spanData) {
        return;
    }
    SpanPtr spanPb = (SpanPtr)spanData;
    thread_local std::string data;
    spanPb->set_end_time_unix_nano(MsUtils::GetCurrentTimeInNanoseconds());

    google::protobuf::ArenaOptions arena_options;
    // It's easy to allocate datas larger than 1024 when we populate basic resource and attributes
    arena_options.initial_block_size = 1024;
    // When in batch mode, it's easy to export a large number of spans at once, we can alloc a larger
    // block to reduce memory fragments.
    arena_options.max_block_size = 65536;

    opentelemetry::proto::collector::trace::v1::ExportTraceServiceRequest response{};
    auto resourceSpans = response.add_resource_spans();
    *resourceSpans->mutable_resource() = gResourceProto_;
    auto scopeSpan = resourceSpans->add_scope_spans();

    opentelemetry::proto::common::v1::InstrumentationScope instrumentation_scope_proto;
    *instrumentation_scope_proto.mutable_name() = std::move(moduleName_);
    *scopeSpan->mutable_scope() = std::move(instrumentation_scope_proto);

    *scopeSpan->add_spans() = std::move(*spanPb);

    if (response.SerializeToString(&data)) {
        msServiceProfiler::SendTracer(std::move(data));
    }

    delete spanPb;
}

// 将十六进制字符串转换为vector<uint8_t>
template <int size>
void hexStringToBytes(const std::string &hex, std::array<uint8_t, size> &bytes)
{
    if (hex.length() % 2 != 0) {
        return;
    }

    for (size_t i = 0; i < hex.length() / 2 && i < size; i++) {
        std::string byteString = hex.substr(i * 2, 2);
        bytes.at(i) = static_cast<uint8_t>(std::stoul(byteString, nullptr, 16));
    }
}

TraceId hexStr2TraceId(const std::string &traceStr)
{
    TraceId traceId = {0, 0};
    if (traceStr.size() == 32) {
        hexStringToBytes<16>(traceStr, traceId.as_char);
    }
    return traceId;
}

SpanId hexStr2SpanId(const std::string &spanStr)
{
    SpanId spanId(0);
    if (spanStr.size() == 16) {
        hexStringToBytes<8>(spanStr, spanId.as_char);
    }
    return spanId;
}

TraceContextInfo ParseHttpCtx(const std::string &traceParent, const std::string &traceB3)
{
    if (!traceParent.empty()) {
        // traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
        // <version>-<trace-id>-<parent-id>-<trace-flags>

        auto splitValues = MsUtils::SplitStrToVector(traceParent, '-');
        if (splitValues.size() != 4) {
            return TraceContextInfo{{0, 0}, 0, false};
        }
        return TraceContextInfo{
            hexStr2TraceId(splitValues.at(1)), hexStr2SpanId(splitValues.at(2)), splitValues.at(3) == "01"};
    } else if (!traceB3.empty()) {
        // b3: 0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-1-a0a0a0a0a0a0a0a0
        // b3: <TraceId>-<SpanId>-<Sampled>-<ParentSpanId>

        auto splitValues = MsUtils::SplitStrToVector(traceB3, '-');
        if (splitValues.size() == 2) {
            return TraceContextInfo{hexStr2TraceId(splitValues.at(0)), hexStr2SpanId(splitValues.at(1)), false};
        } else if (splitValues.size() == 3 || splitValues.size() == 4) {
            return TraceContextInfo{hexStr2TraceId(splitValues.at(0)),
                hexStr2SpanId(splitValues.at(1)),
                splitValues.at(2) == "1" || splitValues.at(2) == "d"};
        } else {
            return TraceContextInfo{{0, 0}, 0, false};
        }
    } else {
        return TraceContextInfo{{0, 0}, 0, false};
    }
}
