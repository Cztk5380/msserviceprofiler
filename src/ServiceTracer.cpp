/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceTracer.h"
#include "msServiceProfiler/ServiceProfilerInterface.h"

namespace msServiceProfiler {

bool IsTraceEnvEnable()
{
    static bool traceEnable = MsUtils::GetEnvAsString("MS_TRACE_ENABLE") == "1";
    return traceEnable;
};

void TraceSender::Execute()
{
    PROF_LOGD("Execute");  // LCOV_EXCL_LINE
}

void SendTracer(std::string &&traceMsg)
{
    msServiceProfiler::ServiceTraceThreadSender::GetSender().Send(
        std::move(std::make_unique<msServiceProfiler::TraceSender>(std::move(traceMsg))));
}
}  // namespace msServiceProfiler

bool IsTraceEnable()
{
    static bool traceEnable = msServiceProfiler::IsTraceEnvEnable();
    return traceEnable;
}