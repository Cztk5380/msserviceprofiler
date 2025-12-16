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
#include <cstring>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <climits>
#include <chrono>
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/Utils.h"

namespace MsUtils {

uint32_t GetTid()
{
    thread_local uint32_t tid = static_cast<uint32_t>(syscall(SYS_gettid));
    return tid;
}

bool MakeDirs(const std::string &dirPath)
{
    if (access(dirPath.c_str(), F_OK) == 0) {
        return true;
    }
    auto pathLen = dirPath.size();
    decltype(pathLen) offset = 0;

    do {
        const char *str = strchr(dirPath.c_str() + offset, '/');
        offset = (str == nullptr) ? pathLen : str - dirPath.c_str() + 1;
        std::string curPath = dirPath.substr(0, offset);
        if (access(curPath.c_str(), F_OK) != 0) {
            int ret = mkdir(curPath.c_str(), S_IRWXU | S_IRGRP | S_IXGRP);
            if (ret != 0 && errno != EEXIST) {
                return false;
            }
        }
    } while (offset != pathLen);
    return true;
}

uint64_t GetCurrentTimeInNanoseconds()
{
    // 获取当前时间点
    auto now = std::chrono::high_resolution_clock::now();

    // 转换为从epoch开始的时间跨度
    auto duration = now.time_since_epoch();

    // 转换为纳秒计数
    auto nanoseconds = std::chrono::duration_cast<std::chrono::nanoseconds>(duration);

    // 返回int64_t类型的纳秒数
    return static_cast<uint64_t>(nanoseconds.count());
}

static std::string LocalGetHostName()
{
    char hostname[HOST_NAME_MAX + 1] = {'\0'};  // 分配足够大的缓冲区
    if (gethostname(hostname, sizeof(hostname)) != 0) {
        PROF_LOGE("get hostname failed");  // LCOV_EXCL_LINE
    }
    return std::string(hostname);
}

const std::string &GetHostName()
{
    static std::string hostname = LocalGetHostName();
    return hostname;
}

FailAutoFree::~FailAutoFree()
{
    if (!failed) {
        return;
    }
    for (auto freeFunc : freeFuncArray) {
        if (freeFunc.first != nullptr) {
            freeFunc.first();
            PROF_LOGD("Auto Free: %s", freeFunc.second.c_str());
        }
    }
}

}  // namespace MsUtils