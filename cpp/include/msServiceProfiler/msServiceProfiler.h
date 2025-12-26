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
#ifndef MSSERVICEPROFILER_H
#define MSSERVICEPROFILER_H

#include "Profiler.h"

#define SERVER_PROFILER

#define ProfLevel0 msServiceProfiler::L0
#define ProfLevel1 msServiceProfiler::L1
#define ProfLevel2 msServiceProfiler::L2

#define ProfilerL0 msServiceProfiler::Profiler<msServiceProfiler::L0>
#define ProfilerL1 msServiceProfiler::Profiler<msServiceProfiler::L1>
#define ProfilerL2 msServiceProfiler::Profiler<msServiceProfiler::L2>

#define ITER_TYPE(_VECTOR_) decltype((_VECTOR_).begin())

#define PRIVATE_MACRO_VAR_ARGS_IMPL_COUNT(_1, _2, N, ...) N
#define PRIVATE_MACRO_VAR_ARGS_IMPL(args) PRIVATE_MACRO_VAR_ARGS_IMPL_COUNT args
#define PRIVATE_COUNT_MACRO_VAR_ARGS(...) PRIVATE_MACRO_VAR_ARGS_IMPL((__VA_ARGS__, 2, 1))

#define PRIVATE_MACRO_CHOOSE_HELPER1(M, count) M##count
#define PRIVATE_MACRO_CHOOSE_HELPER(M, count) PRIVATE_MACRO_CHOOSE_HELPER1(M, count)

#define PRIVATE_PROF_STMT(_STMT) _STMT
#define PRIVATE_PROF_STMT_LEVEL(_LEVEL, _STMT) msServiceProfiler::Profiler<msServiceProfiler::_LEVEL>()._STMT

#define PRIVATE_PROF1 PRIVATE_PROF_STMT
#define PRIVATE_PROF2 PRIVATE_PROF_STMT_LEVEL

#define PROF(...) PRIVATE_MACRO_CHOOSE_HELPER(PRIVATE_PROF, PRIVATE_COUNT_MACRO_VAR_ARGS(__VA_ARGS__))(__VA_ARGS__)
#define MONITOR(...) PROF(__VA_ARGS__)

#endif  // MSSERVICEPROFILER_H
