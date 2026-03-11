/* -------------------------------------------------------------------------
 * This file is part of the MindStudio project.
 * Copyright (c) 2025 Huawei Technologies Co.,Ltd.
 *
 * MindStudio is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *
 *          http://license.coscl.org.cn/MulanPSL2
 *
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 * -------------------------------------------------------------------------
*/

#include <iostream>
#include <string>
#include <vector>
#include <array>
#include <limits>
#include <atomic>
#include <cstdint>
#include <random>
#include <mutex>
#include <new>
#include <cstdlib>

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
opentelemetry::proto::resource::v1::Resource &getResourceProto()
{
    return gResourceProto_;
}
#endif

void ResAddAttr(const char *key, const char *value)
{
    if (key == nullptr || value == nullptr) {
        return;
    }
    try {
        auto attr = gResourceProto_.add_attributes();
        attr->set_key(key);
        attr->mutable_value()->set_string_value(value);
    } catch (const std::exception &e) {
        PROF_LOGE("cannot set attr. %s", e.what());  // LCOV_EXCL_LINE
    }
}

TRACE_SPAN_DATA NewSpanData(const char *spanName)
{
    if (spanName == nullptr) {
        return nullptr;
    }
    opentelemetry::proto::trace::v1::Span *spanPb = new (std::nothrow) opentelemetry::proto::trace::v1::Span();
    if (spanPb == nullptr) {
        return nullptr;
    }
    try {
        spanPb->set_name(spanName);
    } catch (const std::exception &e) {
        PROF_LOGE("cannot set span name. %s", e.what());  // LCOV_EXCL_LINE
    }
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
    try {
        attribute->set_key(attrName);
        attribute->mutable_value()->set_string_value(value);
    } catch (const std::exception &e) {
        PROF_LOGE("cannot set span name. %s", e.what());  // LCOV_EXCL_LINE
    }
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
        try {
            spanPb->mutable_status()->set_message(msg);
        } catch (const std::exception &e) {
            PROF_LOGE("cannot set status message. %s", e.what());  // LCOV_EXCL_LINE
        }
    }
}

struct TraceEnvConfig {
    bool autoTraceEnabled = false;
    bool errorOnlySamplingEnabled = false;
    int sampleRateN = 0;
};

// 解析 "0"/"1" 型环境变量
static bool ParseEnvFlag(const char *envStr, bool &out, const char *envName)
{
    if (envStr == nullptr || envStr[0] == '\0') {
        return false;
    }
    std::string value(envStr);
    if (value == "1") {
        out = true;
        return true;
    }
    if (value == "0") {
        out = false;
        return true;
    }
    PROF_LOGW("%s invalid value: %s, expect 0 or 1, ignore.", envName, envStr);
    return false;
}

// 解析正整数环境变量，要求全部为数字且 >0
static bool ParsePositiveIntFromEnv(const char *envStr, int &out)
{
    if (envStr == nullptr || envStr[0] == '\0') {
        return false;
    }
    uint64_t value = 0;
    for (const char *p = envStr; *p != '\0'; ++p) {
        if (*p < '0' || *p > '9') {
            return false;
        }
        value = value * 10 + static_cast<uint64_t>(*p - '0');
        if (value > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
            return false;
        }
    }
    if (value == 0) {
        return false;
    }
    out = static_cast<int>(value);
    return true;
}

static TraceEnvConfig &GetTraceEnvConfig()
{
    static TraceEnvConfig config;
    static std::once_flag initFlag;
    std::call_once(initFlag, []() {
        // MS_PROFILER_AUTO_TRACE: "1" 开启自动 trace，"0" 关闭，其他值视为无效
        if (const char *autoTraceEnv = std::getenv("MS_PROFILER_AUTO_TRACE")) {
            bool flag = false;
            if (ParseEnvFlag(autoTraceEnv, flag, "MS_PROFILER_AUTO_TRACE")) {
                config.autoTraceEnabled = flag;
            }
        }

        // MS_PROFILER_SAMPLE_ERROR: "1" 开启错误采样，仅保留 ERROR；"0" 关闭，其他值为无效
        if (const char *errorOnlyEnv = std::getenv("MS_PROFILER_SAMPLE_ERROR")) {
            bool flag = false;
            if (ParseEnvFlag(errorOnlyEnv, flag, "MS_PROFILER_SAMPLE_ERROR")) {
                config.errorOnlySamplingEnabled = flag;
            }
        }

        // MS_PROFILER_SAMPLE_RATE: 表示每多少次请求中采样一次，例如 100 表示每 100 次请求采样 1 次
        // 采样率：>0 表示每 sampleRateN 次请求中采样 1 次；<=0 表示不启用概率采样
        if (const char *rateEnv = std::getenv("MS_PROFILER_SAMPLE_RATE")) {
            int rate = 0;
            if (ParsePositiveIntFromEnv(rateEnv, rate)) {
                config.sampleRateN = rate;
            } else {
                PROF_LOGW("MS_PROFILER_SAMPLE_RATE invalid value: %s, expect positive integer, ignore.", rateEnv);
            }
        }
    });
    return config;
}

void SpanEndAndFree(TRACE_SPAN_DATA spanData, std::string &&moduleName_)
{
    if (!spanData) {
        return;
    }
    SpanPtr spanPb = (SpanPtr)spanData;
    thread_local std::string data;
    spanPb->set_end_time_unix_nano(MsUtils::GetCurrentTimeInNanoseconds());

    auto &cfg = GetTraceEnvConfig();
    if (cfg.errorOnlySamplingEnabled) {
        if (spanPb->status().code() != opentelemetry::proto::trace::v1::Status::STATUS_CODE_ERROR) {
            PROF_LOGD("SpanEndAndFree skip span by error-only sampling, status=%d",
                static_cast<int>(spanPb->status().code()));
            delete spanPb;
            return;
        } else {
            PROF_LOGD("SpanEndAndFree keep error span under error-only sampling, status=%d",
                static_cast<int>(spanPb->status().code()));
        }
    }

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
    try {
        *instrumentation_scope_proto.mutable_name() = moduleName_;
    } catch (const std::exception &e) {
        PROF_LOGE("cannot set scope. %s", e.what());  // LCOV_EXCL_LINE
    }
    *scopeSpan->mutable_scope() = std::move(instrumentation_scope_proto);

    *scopeSpan->add_spans() = std::move(*spanPb);

    if (response.SerializeToString(&data)) {
        msServiceProfiler::SendTracer(std::move(data));
    }

    delete spanPb;
}

std::array<uint8_t, 256> generateHexCharToValueTable()
{
    std::array<uint8_t, 256> table = {};
    for (unsigned char c = 0; c < 200; ++c) {
        if (c >= '0' && c <= '9') {
            table[c] = c - '0';
        } else if (c >= 'A' && c <= 'F') {
            table[c] = c - 'A' + 10;
        } else if (c >= 'a' && c <= 'f') {
            table[c] = c - 'a' + 10;
        } else {
            table[c] = 0xFF;  // Invalid character
        }
    }
    return table;
}

// 将十六进制字符串转换为vector<uint8_t>
template <int size>
void hexStringToBytes(const std::string &hex, std::array<uint8_t, size> &bytes)
{
    const static auto hexCharToValueTable = generateHexCharToValueTable();
    if (hex.length() != size * 2) {
        throw std::invalid_argument("Hex string length must be exactly " + std::to_string(size * 2) + " characters");
    }

    for (size_t i = 0; i < hex.length() / 2; i++) {
        uint8_t high = hexCharToValueTable[static_cast<unsigned char>(hex[i * 2])];
        uint8_t low = hexCharToValueTable[static_cast<unsigned char>(hex[i * 2 + 1])];

        if (high == 0xFF || low == 0xFF) {
            throw std::invalid_argument("Invalid hex character");
        }
        // Combine the high and low nibbles to form the byte
        bytes[i] = (high << 4) | low;
    }
}

bool hexStr2TraceId(const std::string &traceStr, TraceId &traceId)
{
    constexpr int TRACE_BYTE_SIZE = 16;
    if (traceStr.size() != TRACE_BYTE_SIZE * 2) {
        PROF_LOGE("Cannot parse hex str, %s, Invalid length.", traceStr.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    try {
        hexStringToBytes<TRACE_BYTE_SIZE>(traceStr, traceId.as_char);
        return true;
    } catch (const std::exception &e) {
        PROF_LOGE("cannot parse hex str %s, %s ", traceStr.c_str(), e.what());  // LCOV_EXCL_LINE
        return false;
    }
}

bool hexStr2SpanId(const std::string &spanStr, SpanId &spanId)
{
    constexpr int SPAN_BYTE_SIZE = 8;
    if (spanStr.size() != SPAN_BYTE_SIZE * 2) {
        PROF_LOGE("Cannot parse hex str, %s, Invalid length.", spanStr.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    try {
        hexStringToBytes<SPAN_BYTE_SIZE>(spanStr, spanId.as_char);
        return true;
    } catch (const std::exception &e) {
        PROF_LOGE("cannot parse hex str %s, %s ", spanStr.c_str(), e.what());  // LCOV_EXCL_LINE
        return false;
    }
}

// 概率采样：MS_PROFILER_SAMPLE_RATE=N 表示 N 条请求里采 1 条，仅在 sampleFlag 为 true 时生效
static bool applyProbabilitySampling(bool sampleFlag)
{
    if (!sampleFlag) {
        return false;
    }
    auto &cfg = GetTraceEnvConfig();
    // 未配置或配置非法时，不额外做概率过滤
    if (cfg.sampleRateN <= 0) {
        return true;
    }
    // 进程级原子计数器，保证多线程下概率采样在进程内正确生效
    static std::atomic<uint64_t> counter{0};
    uint64_t idx = counter.fetch_add(1) % static_cast<uint64_t>(cfg.sampleRateN);
    bool sampled = (idx == 0);
    
    PROF_LOGD("probability sampling (deterministic): N=%d, idx=%llu, sampled=%d",
        cfg.sampleRateN, static_cast<unsigned long long>(idx), sampled);
    return sampled;
}

TraceContextInfo ParseHttpCtx(const std::string &traceParent, const std::string &traceB3)
{
    std::string strTraceParent = traceParent.c_str();
    std::string strTraceB3 = traceB3.c_str();
    TraceId traceId = {0, 0};
    SpanId spanId(0);
    bool parseSuccessFlag = true;
    bool sampleFlag = false;

    constexpr decltype(strTraceParent.length()) MAX_TRACE_LENGTH = 256;
    if (strTraceParent.length() > MAX_TRACE_LENGTH || strTraceB3.length() > MAX_TRACE_LENGTH) {
        LOG_ONCE_E("traceparent Format not recognized. ");
        return TraceContextInfo{{0, 0}, 0, false};
    }

    if (!strTraceParent.empty()) {
        // traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
        // <version>-<trace-id>-<parent-id>-<trace-flags>
        auto splitValues = MsUtils::SplitStrToVector(strTraceParent, '-', true);
        if (splitValues.size() != 4) {
            LOG_ONCE_E("traceparent Format not recognized. ");
            return TraceContextInfo{{0, 0}, 0, false};
        }
        parseSuccessFlag = hexStr2TraceId(splitValues.at(1), traceId);
        parseSuccessFlag = hexStr2SpanId(splitValues.at(2), spanId) && parseSuccessFlag;
        sampleFlag = splitValues.at(3) == "01";

        return TraceContextInfo{traceId, spanId, parseSuccessFlag && sampleFlag};
    } else if (!strTraceB3.empty()) {
        // b3: 0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-1-a0a0a0a0a0a0a0a0
        // b3: <TraceId>-<SpanId>-<Sampled>-<ParentSpanId>

        auto splitValues = MsUtils::SplitStrToVector(strTraceB3, '-', true);
        if (splitValues.size() >= 2) {
            parseSuccessFlag = hexStr2TraceId(splitValues.at(0), traceId);
            parseSuccessFlag = hexStr2SpanId(splitValues.at(1), spanId) && parseSuccessFlag;
        } else {
            LOG_ONCE_E("b3 Format not recognized. ");
            return TraceContextInfo{{0, 0}, 0, false};
        }

        if (splitValues.size() == 2) {
            return TraceContextInfo{traceId, spanId, false};
        } else if (splitValues.size() == 3 || splitValues.size() == 4) {
            sampleFlag = splitValues.at(2) == "1" || splitValues.at(2) == "d";
            return TraceContextInfo{traceId, spanId, parseSuccessFlag && sampleFlag};
        }
    } else {
        // traceparent 与 traceb3 均为空时，若环境变量 MS_PROFILER_AUTO_TRACE 为 "1" 时自动生成 trace_id
        auto &cfg = GetTraceEnvConfig();
        if (cfg.autoTraceEnabled) {
            PROF_LOGD("MS_PROFILER_AUTO_TRACE enabled, generate new trace context.");
            TraceId newTraceId(msServiceProfiler::TraceContext::GenTraceId(),
                msServiceProfiler::TraceContext::GenSpanId());
            SpanId newSpanId(msServiceProfiler::TraceContext::GenSpanId());
            PROF_LOGD("auto generated TraceId high=0x%016llx low=0x%016llx",
                static_cast<unsigned long long>(newTraceId.as_uint64[0]),
                static_cast<unsigned long long>(newTraceId.as_uint64[1]));
            return TraceContextInfo{
                newTraceId, newSpanId, applyProbabilitySampling(true)};
        }
        LOG_ONCE_D("no trace info. ");
        return TraceContextInfo{{0, 0}, 0, false};
    }
    return TraceContextInfo{{0, 0}, 0, false};
}
