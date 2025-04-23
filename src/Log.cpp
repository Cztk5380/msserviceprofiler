/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <cstdlib>
#include <cstring>
#include "msServiceProfiler/Log.h"

namespace {
    // 静态全局变量存储当前日志级别
    ProfLogLevel g_profLogLevel = ProfLogLevel::PROF_LOG_INFO;
}

void ProfLogInit()
{
    const char* envLevel = getenv("PROF_LOG_LEVEL");
    if (envLevel == nullptr) {
        g_profLogLevel = ProfLogLevel::PROF_LOG_INFO; // 默认级别
        return;
    }

    if (strcmp(envLevel, "DEBUG") == 0) {
        g_profLogLevel = ProfLogLevel::PROF_LOG_DEBUG;
    } else if (strcmp(envLevel, "INFO") == 0) {
        g_profLogLevel = ProfLogLevel::PROF_LOG_INFO;
    } else if (strcmp(envLevel, "WARNING") == 0) {
        g_profLogLevel = ProfLogLevel::PROF_LOG_WARNING;
    } else if (strcmp(envLevel, "ERROR") == 0) {
        g_profLogLevel = ProfLogLevel::PROF_LOG_ERROR;
    } else if (strcmp(envLevel, "NONE") == 0) {
        g_profLogLevel = ProfLogLevel::PROF_LOG_NONE;
    } else {
        g_profLogLevel = ProfLogLevel::PROF_LOG_INFO; // 默认级别
    }
}

ProfLogLevel ProfLogGetLevel()
{
    return g_profLogLevel;
}

void ProfLogSetLevel(ProfLogLevel level)
{
    g_profLogLevel = level;
}
