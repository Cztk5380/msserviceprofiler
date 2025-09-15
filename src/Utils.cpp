/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */
#include <cstring>
#include <unistd.h>
#include <sys/stat.h>
#include <chrono>
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
}