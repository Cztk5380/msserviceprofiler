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

#include <gtest/gtest.h>
#include <iostream>
#include <string>
#include <vector>
#include <array>
#include <limits>
#include <cstdint>
#include <random>
#include <mutex>

#include <google/protobuf/util/json_util.h>
#include "opentelemetry/proto/trace/v1/trace.pb.h"
#include "opentelemetry/proto/collector/trace/v1/trace_service.pb.h"

#include "msServiceProfiler/ServiceProfilerInterface.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceTracer.h"
#include "msServiceProfiler/Tracer.h"

extern opentelemetry::proto::resource::v1::Resource &getResourceProto();
extern bool hexStr2TraceId(const std::string &traceStr, TraceId &traceId);
extern bool hexStr2SpanId(const std::string &spanStr, SpanId &spanId);
extern void SpanFillCtxData(TRACE_SPAN_DATA spanData, TraceId traceid, SpanId spanid, SpanId pSpanid);
using SpanPtr = opentelemetry::proto::trace::v1::Span *;
template <int cnt>
std::array<uint8_t, cnt> stringToByteArray(const std::string &str)
{
    std::array<uint8_t, cnt> arr;
    std::copy(str.begin(), str.end(), arr.begin());
    return arr;
}

class TracerTest : public ::testing::Test {
protected:
    void SetUp() override
    {
        // 在每个测试用例之前执行的设置代码
    }

    void TearDown() override
    {
        // 在每个测试用例之后执行的清理代码
    }
};

TEST_F(TracerTest, TestResAddAttr)
{
    ResAddAttr("key1", "value1");
    ResAddAttr("key2", "value2");

    EXPECT_EQ(getResourceProto().attributes_size(), 2);
    EXPECT_EQ(getResourceProto().attributes(0).key(), "key1");
    EXPECT_EQ(getResourceProto().attributes(0).value().string_value(), "value1");
    EXPECT_EQ(getResourceProto().attributes(1).key(), "key2");
    EXPECT_EQ(getResourceProto().attributes(1).value().string_value(), "value2");
}

TEST_F(TracerTest, TestNewSpanData)
{
    TRACE_SPAN_DATA spanData = NewSpanData("testSpan");
    SpanPtr span_pb = (SpanPtr)spanData;

    EXPECT_EQ(span_pb->name(), "testSpan");
    EXPECT_EQ(span_pb->kind(), opentelemetry::proto::trace::v1::Span_SpanKind_SPAN_KIND_SERVER);
    EXPECT_EQ(span_pb->flags(), opentelemetry::proto::trace::v1::SPAN_FLAGS_CONTEXT_HAS_IS_REMOTE_MASK);

    delete span_pb;
}

TEST_F(TracerTest, TestSpanActivate)
{
    TRACE_SPAN_DATA spanData = NewSpanData("testSpan");
    SpanPtr span_pb = (SpanPtr)spanData;

    uint64_t startTime = 1234567890;
    SpanActivate(spanData, startTime);

    EXPECT_EQ(span_pb->start_time_unix_nano(), startTime);

    delete span_pb;
}

TEST_F(TracerTest, TestSpanFillCtxData)
{
    TRACE_SPAN_DATA spanData = NewSpanData("testSpan");
    SpanPtr span_pb = (SpanPtr)spanData;

    TraceId traceId = {0, 0};
    SpanId spanId(0);
    SpanId parentSpanId(0);

    EXPECT_TRUE(hexStr2TraceId("0af7651916cd43dd8448eb211c80319c", traceId));
    EXPECT_TRUE(hexStr2SpanId("b7ad6b7169203331", spanId));
    EXPECT_TRUE(hexStr2SpanId("a0a0a0a0a0a0a0a0", parentSpanId));

    SpanFillCtxData(spanData, traceId, spanId, parentSpanId);

    EXPECT_EQ(stringToByteArray<16>(span_pb->trace_id()), traceId.as_char);
    EXPECT_EQ(stringToByteArray<8>(span_pb->span_id()), spanId.as_char);
    EXPECT_EQ(stringToByteArray<8>(span_pb->parent_span_id()), parentSpanId.as_char);

    delete span_pb;
}

TEST_F(TracerTest, TestSpanAddAttribute)
{
    TRACE_SPAN_DATA spanData = NewSpanData("testSpan");
    SpanPtr span_pb = (SpanPtr)spanData;

    SpanAddAttribute(spanData, "attr1", "value1");
    SpanAddAttribute(spanData, "attr2", "value2");

    EXPECT_EQ(span_pb->attributes_size(), 2);
    EXPECT_EQ(span_pb->attributes(0).key(), "attr1");
    EXPECT_EQ(span_pb->attributes(0).value().string_value(), "value1");
    EXPECT_EQ(span_pb->attributes(1).key(), "attr2");
    EXPECT_EQ(span_pb->attributes(1).value().string_value(), "value2");

    delete span_pb;
}

TEST_F(TracerTest, TestSpanSetStatus)
{
    TRACE_SPAN_DATA spanData = NewSpanData("testSpan");
    SpanPtr span_pb = (SpanPtr)spanData;

    SpanSetStatus(spanData, true, "");
    EXPECT_EQ(span_pb->status().code(), opentelemetry::proto::trace::v1::Status::STATUS_CODE_OK);
    EXPECT_EQ(span_pb->status().message(), "");

    SpanSetStatus(spanData, false, "Error message");
    EXPECT_EQ(span_pb->status().code(), opentelemetry::proto::trace::v1::Status::STATUS_CODE_ERROR);

    delete span_pb;
}

TEST_F(TracerTest, TestSpanEndAndFree)
{
    TRACE_SPAN_DATA spanData = NewSpanData("testSpan");
    SpanPtr span_pb = (SpanPtr)spanData;

    SpanEndAndFree(spanData, "testModule");
}

TEST_F(TracerTest, TestParseHttpCtx)
{
    TraceId traceId = {0, 0};
    SpanId spanId(0);
    EXPECT_TRUE(hexStr2TraceId("0af7651916cd43dd8448eb211c80319c", traceId));
    EXPECT_TRUE(hexStr2SpanId("b7ad6b7169203331", spanId));

    TraceContextInfo ctx1 = ParseHttpCtx("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01", "");

    EXPECT_EQ(std::get<0>(ctx1).as_char, traceId.as_char);
    EXPECT_EQ(std::get<1>(ctx1).as_char, spanId.as_char);
    EXPECT_TRUE(std::get<2>(ctx1));

    TraceContextInfo ctx2 = ParseHttpCtx("", "0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-1");
    EXPECT_EQ(std::get<0>(ctx2).as_char, traceId.as_char);
    EXPECT_EQ(std::get<1>(ctx2).as_char, spanId.as_char);
    EXPECT_TRUE(std::get<2>(ctx2));

    TraceContextInfo ctx3 = ParseHttpCtx("", "0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-0");
    EXPECT_EQ(std::get<0>(ctx3).as_char, traceId.as_char);
    EXPECT_EQ(std::get<1>(ctx3).as_char, spanId.as_char);
    EXPECT_FALSE(std::get<2>(ctx3));

    TraceContextInfo ctx4 = ParseHttpCtx("", "");
    EXPECT_EQ(std::get<0>(ctx4).as_char, (TraceId{0, 0}).as_char);
    EXPECT_EQ(std::get<1>(ctx4).as_char, SpanId(0).as_char);
    EXPECT_FALSE(std::get<2>(ctx4));
}
