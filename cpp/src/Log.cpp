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

#include <cstdlib>
#include <cstring>
#include "msServiceProfiler/Log.h"

namespace msServiceProfiler {
    ProfLogLevel g_profLogLevel = ProfLogLevel::PROF_LOG_INFO;
}

void msServiceProfiler::ProfLogInit()
{
    const char* envLevel = getenv("PROF_LOG_LEVEL");
    if (envLevel == nullptr) {
        g_profLogLevel = ProfLogLevel::PROF_LOG_INFO; // 默认级别
        return;
    }

    if (strcmp(envLevel, "DEBUG") == 0) {
        g_profLogLevel = msServiceProfiler::ProfLogLevel::PROF_LOG_DEBUG;
    } else if (strcmp(envLevel, "INFO") == 0) {
        g_profLogLevel = msServiceProfiler::ProfLogLevel::PROF_LOG_INFO;
    } else if (strcmp(envLevel, "WARNING") == 0) {
        g_profLogLevel = msServiceProfiler::ProfLogLevel::PROF_LOG_WARNING;
    } else if (strcmp(envLevel, "ERROR") == 0) {
        g_profLogLevel = msServiceProfiler::ProfLogLevel::PROF_LOG_ERROR;
    } else if (strcmp(envLevel, "NONE") == 0) {
        g_profLogLevel = msServiceProfiler::ProfLogLevel::PROF_LOG_NONE;
    } else {
        g_profLogLevel = ProfLogLevel::PROF_LOG_INFO; // 默认级别
    }
}

msServiceProfiler::ProfLogLevel msServiceProfiler::ProfLogGetLevel()
{
    return g_profLogLevel;
}

void msServiceProfiler::ProfLogSetLevel(ProfLogLevel level)
{
    g_profLogLevel = level;
}
