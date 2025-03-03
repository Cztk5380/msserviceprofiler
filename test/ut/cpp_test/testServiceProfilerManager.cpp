/*
* Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <vector>
#include <chrono>

#include "msServiceProfiler/msServiceProfiler.h"

void MarkEventLongAttr(const char *msg);

using namespace msServiceProfiler;

// Test suite for StartSpan function
TEST(ProfilerTest, StartSpan)
{
    SpanHandle span = StartSpan();
    ASSERT_GE(span, 0U);
}