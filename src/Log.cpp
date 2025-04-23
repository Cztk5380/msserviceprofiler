/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <cstdlib>
#include <cstring>
#include "msServiceProfiler/Log.h"

void ProfLogInit()
{
    const char* envLevel = getenv("PROF_LOG_LEVEL");
    if (envLevel == nullptr) {
        g_prof_log_level = ProfLogLevel::PROF_LOG_INFO; // 默认级别
        return;
    }

    if (strcmp(envLevel, "DEBUG") == 0) {
        g_prof_log_level = ProfLogLevel::PROF_LOG_DEBUG;
    } else if (strcmp(envLevel, "INFO") == 0) {
        g_prof_log_level = ProfLogLevel::PROF_LOG_INFO;
    } else if (strcmp(envLevel, "WARNING") == 0) {
        g_prof_log_level = ProfLogLevel::PROF_LOG_WARNING;
    } else if (strcmp(envLevel, "ERROR") == 0) {
        g_prof_log_level = ProfLogLevel::PROF_LOG_ERROR;
    } else if (strcmp(envLevel, "NONE") == 0) {
        g_prof_log_level = ProfLogLevel::PROF_LOG_NONE;
    } else {
        g_prof_log_level = ProfLogLevel::PROF_LOG_INFO; // 默认级别
    }
}

ProfLogLevel ProfLogGetLevel()
{
    return g_prof_log_level;
}

void prof_log_set_level(ProfLogLevel level)
{
    g_prof_log_level = level;
}
