/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
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

#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <algorithm>
#include <cstring>
#include <ctime>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <map>

#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mstx/ms_tools_ext.h"

#include "../include/msServiceProfiler/ServiceProfilerManager.h"

constexpr int MAX_TX_MSG_LEN = 128;
constexpr int MAX_DEVICE_NUM = 128;
constexpr int STRING_TO_UINT_BASE = 10;

#define PROF_LOGD(...)       \
    do {                     \
        printf(__VA_ARGS__); \
        printf("\n");        \
    } while (0)

#define PROF_LOGE(...)       \
    do {                     \
        printf(__VA_ARGS__); \
        printf("\n");        \
    } while (0)

SpanHandle StartSpan()
{
    return mstxRangeStartA("", nullptr);
}

void MarkSpanAttr(const char *msg, SpanHandle spanHandle)
{
    std::string spanTag;
    spanTag.reserve(MAX_TX_MSG_LEN);
    spanTag.append("span=").append(std::to_string(spanHandle)).append("|");
    auto spanTagSize = spanTag.size();
    auto msgLen = strlen(msg);
    auto maxMarkSize = MAX_TX_MSG_LEN - spanTagSize - 1;
    if (maxMarkSize <= 0) {
        return;
    }
    const char *oriMsgStart = msg;
    while (static_cast<decltype(msgLen)>(oriMsgStart - msg) < msgLen) {
        spanTag.append(oriMsgStart, maxMarkSize);
        oriMsgStart += maxMarkSize;
        MarkEvent(spanTag.c_str());
        spanTag.resize(spanTagSize);
    }
}

void EndSpan(SpanHandle spanHandle)
{
    mstxRangeEnd(spanHandle);
}

void MarkEventLongAttr(const char *msg)
{
    auto spanHandle = StartSpan();
    MarkSpanAttr(msg, spanHandle);
}

void MarkEvent(const char *msg)
{
    if (strlen(msg) > MAX_TX_MSG_LEN) {
        MarkEventLongAttr(msg);
    }
    mstxMarkA(msg, nullptr);
}

void StartServerProfiler()
{
    msServiceProfiler::ServiceProfilerManager::GetInstance().StartProfiler();
}

void StopServerProfiler()
{
    msServiceProfiler::ServiceProfilerManager::GetInstance().StopProfiler();
}

bool IsEnable(uint32_t level)
{
    return msServiceProfiler::ServiceProfilerManager::GetInstance().IsEnable(level);
}

namespace msServiceProfiler {
    static inline std::string TrimStr(const std::string &str)
    {
        auto start = str.find_first_not_of(" \t\n\v\f\r");
        if (start == std::string::npos) {
            return "";
        };
        auto end = str.find_last_not_of(" \t\n\v\f\r");
        return str.substr(start, end - start + 1);
    }

    static inline unsigned long Str2Uint(const std::string &str)
    {
        char *endPtr;
        return std::strtoul(str.c_str(), &endPtr, STRING_TO_UINT_BASE);
    }

    static inline std::pair<std::string, std::string> SplitStr(const std::string &str, char splitChar)
    {
        auto start = str.find_first_of(splitChar);
        if (start == std::string::npos) {
            return {"", ""};
        } else {
            return {str.substr(0, start), str.substr(start + 1)};
        }
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
                if (mkdir(curPath.c_str(), S_IRWXU | S_IRGRP | S_IXGRP) != 0) {
                    return false;
                }
            }
        } while (offset != pathLen);
        return true;
    }

    ServiceProfilerManager &ServiceProfilerManager::GetInstance()
    {
        static ServiceProfilerManager manager;
        return manager;
    }

    ServiceProfilerManager::ServiceProfilerManager()
    {
        std::string homePath = getenv("HOME") ? getenv("HOME") : "";
        profPath_.append(homePath).append("/.ms_server_profiler/");
        ReadConfig();
        if (enable_) {
            StartProfiler();
        }
    }

    void ServiceProfilerManager::ReadConfig()
    {
        time_t now = time(nullptr);
        tm *ltm = std::localtime(&now);

        std::string strConfigPath = getenv("PROF_CONFIG_PATH") ? getenv("PROF_CONFIG_PATH") : "";
        if (!strConfigPath.empty() && access(strConfigPath.c_str(), F_OK) == 0) {
            std::ifstream configFile;
            configFile.open(strConfigPath.c_str(), std::ios::in);
            char lineData[256] = {0};
            while (configFile.rdstate() != std::ios_base::eofbit) {
                configFile.getline(lineData, sizeof(lineData) - 1);
                if (configFile.rdstate() & std::ios_base::eofbit) {
                    break;
                }

                auto kvPair = SplitStr(lineData, '=');

                std::string key(TrimStr(kvPair.first));
                std::string value(TrimStr(kvPair.second));

                ReadEnable(key, value) || ReadProfPath(key, value) || ReadLevel(key, value);
            }
        }
        profPath_.append(std::to_string(ltm->tm_mon + 1))
                .append(std::to_string(ltm->tm_mday))
                .append("-")
                .append(std::to_string(ltm->tm_hour))
                .append(std::to_string(ltm->tm_min))
                .append("/");
    }

    bool ServiceProfilerManager::ReadEnable(const std::string &key, const std::string &value)
    {
        if (key == "enable") {
            enable_ = value == "1";
            return true;
        } else {
            return false;
        }
    }

    bool ServiceProfilerManager::ReadProfPath(const std::string &key, const std::string &value)
    {
        if (key == "prof_dir") {
            if (!value.empty()) {
                profPath_ = value;
                if (value.back() != '/') {
                    profPath_.append("/");
                }
            }
            return true;
        } else {
            return false;
        }
    }

    bool ServiceProfilerManager::ReadLevel(const std::string &key, const std::string &value)
    {
        static const std::map<std::string, Level> enumMap = {
            {"ERROR", Level::ERROR},
            {"INFO", Level::INFO},
            {"DETAILED", Level::DETAILED},
            {"VERBOSE", Level::VERBOSE},
        };

        if (key == "profiler_level") {
            level_ = Str2Uint(value);
            if (level_ == 0) {
                std::string valueUpper = value;
                std::transform(valueUpper.begin(), valueUpper.end(), valueUpper.begin(), [](char const &c) {
                    return std::toupper(c);
                });
                if (enumMap.find(valueUpper) != enumMap.end()) {
                    level_ = enumMap.at(valueUpper);
                } else {
                    level_ = Level::INFO;
                }
            }
            return true;
        } else {
            return false;
        }
    }

    void ServiceProfilerManager::StartProfiler()
    {
        if (started_) {
            return;
        }
        if (!MakeDirs(profPath_)) {
            PROF_LOGE("create path(%s) failed", profPath_.c_str());
        }
        PROF_LOGD("prof path: %s", profPath_.c_str());

        uint32_t profSwitch = ACL_PROF_MSPROFTX | ACL_PROF_TASK_TIME;
        uint32_t deviceIdList[MAX_DEVICE_NUM] = {0};

        aclError retInit = aclInit(nullptr);
        if (retInit != ACL_ERROR_NONE) {
            PROF_LOGE("acl init failed, ret = %d", retInit);
        }

        aclError ret = aclprofInit(profPath_.c_str(), profPath_.size());
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof init failed, ret = %d", ret);
            return;
        }

        auto config_ = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_NONE, nullptr, profSwitch);
        if (config_ == nullptr) {
            PROF_LOGE("acl prof crate config failed.");
            enable_ = false;
            return;
        }
        configHandle_ = config_;

        if (retInit == ACL_ERROR_NONE) {
            aclprofSetConfig(ACL_PROF_HOST_SYS, "cpu", strlen("cpu"));
            aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE, "cpu", strlen("cpu"));
            aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE_FREQ, "50", strlen("50"));
        }

        PROF_LOGD("begin to start profiling");
        ret = aclprofStart(config_);
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof start failed, ret = %d", ret);
            enable_ = false;
            return;
        }

        enable_ = true;
        started_ = true;
    }

    void ServiceProfilerManager::StopProfiler()
    {
        if (!started_) {
            return;
        }
        enable_ = false;

        auto config_ = (aclprofConfig *)configHandle_;

        auto ret = aclprofStop(config_);
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof stop failed, ret = %d", ret);
            return;
        }
        ret = aclprofDestroyConfig(config_);
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof destroy config failed, ret = %d", ret);
            return;
        }
        configHandle_ = nullptr;

        ret = aclprofFinalize();
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof finalize failed, ret = %d", ret);
            return;
        }
        started_ = false;
    }
}  // namespace msServiceProfiler