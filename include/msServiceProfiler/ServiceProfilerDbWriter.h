/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef SERVICEPROFILERDBWRITER_H
#define SERVICEPROFILERDBWRITER_H

#include <cstdint>
#include <memory>
#include <string>
#include <vector>
#include <map>
#include <iostream>
#include <fstream>

namespace msServiceProfiler {

enum class ActivityFlag {
    ACTIVITY_FLAG_MARKER_EVENT = 1,
    ACTIVITY_FLAG_MARKER_SPAN = 2,
};

using DbActivityMarker = struct PACKED_MARKER_DB {
    ActivityFlag flag;
    uint64_t timestamp;
    uint64_t endTimestamp;
    uint64_t id;
    uint32_t processId;
    uint32_t threadId;
    std::string message;
};

using DbActivityMeta = struct PACKED_META_DB {
    std::string metaKey;
    std::string metaValue;
};

using DbActivityMarkerPtr = std::unique_ptr<DbActivityMarker>;
using DbActivityMetaPtr = std::unique_ptr<DbActivityMeta>;

void InsertTxData2Writer(std::unique_ptr<DbActivityMarker> activity);
void InsertTxData2Writer(std::unique_ptr<DbActivityMeta> activity);
void CloseTxData2Writer();
void StartTxData2Writer(const std::string &outputPath);
std::string GetHostName();

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
void WaitForAllDump();
#endif
}  // namespace msServiceProfiler

#endif  // SERVICEPROFILERMANAGERMSPTI_H
