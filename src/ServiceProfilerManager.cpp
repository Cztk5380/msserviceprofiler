/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstring>
#include <ctime>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <map>
#include <cmath>

#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mstx/ms_tools_ext.h"

#include "../include/msServiceProfiler/NpuMemoryUsage.h"
#include "../include/msServiceProfiler/Profiler.h"
#include "../include/msServiceProfiler/ServiceProfilerManager.h"


constexpr int MAX_TX_MSG_LEN = 128;
constexpr int MAX_DEVICE_NUM = 128;
constexpr int STRING_TO_UINT_BASE = 10;
constexpr int MILLISECONDS_IN_SECOND = 1000;

// 全局标志位，用于控制线程退出
std::atomic<bool> g_threadRunFlag(true);

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

SpanHandle StartSpanWithName(const char *name)
{
    return mstxRangeStartA(name, nullptr);
}

void MarkSpanAttr(const char *msg, SpanHandle spanHandle)
{
    std::string spanTag;
    spanTag.reserve(MAX_TX_MSG_LEN);
    spanTag.append("span=").append(std::to_string(spanHandle)).append("*");
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
        auto configJson = ReadConfig();
        ReadEnable(configJson);
        ReadProfPath(configJson);
        ReadLevel(configJson);
        ReadCollectConfig(configJson);

        time_t now = time(nullptr);
        tm *ltm = std::localtime(&now);
        profPath_.append(std::to_string(ltm->tm_mon + 1))
                .append(std::to_string(ltm->tm_mday))
                .append("-")
                .append(std::to_string(ltm->tm_hour))
                .append(std::to_string(ltm->tm_min))
                .append("/");

        aclError retInit = aclInit(nullptr);
        if (retInit != ACL_ERROR_NONE) {
            PROF_LOGE("acl init failed, ret = %d", retInit);
        }

        if (enable_) {
            StartProfiler();
        }
        LaunchThread();
    }

    json ServiceProfilerManager::ReadConfig()
    {
        std::string strConfigPath = getenv("PROF_CONFIG_PATH") ? getenv("PROF_CONFIG_PATH") : "";
        json jsonData;
        if (!strConfigPath.empty() && access(strConfigPath.c_str(), F_OK) == 0) {
            std::ifstream configFile; // 单独创建 std::ifstream 对象

            try {
                configFile.open(strConfigPath);
                if (!configFile.good()) {
                    PROF_LOGE("fail to open: %s", strConfigPath.c_str());
                    return jsonData;
                }
            } catch (const std::exception &e) {
                PROF_LOGE("fail to open config file: %s, error: %s", 
                        strConfigPath.c_str(), e.what());
                return jsonData;
            }

            try {
                configFile >> jsonData; // 尝试解析 JSON 数据
            } catch (const std::exception &e) {
                PROF_LOGE("fail to parse file content as json object, config path: %s, error: %s", 
                        strConfigPath.c_str(), e.what());
                configFile.close(); // 确保文件关闭
                return jsonData;
            }

            configFile.close(); // 成功解析后关闭文件
            if (jsonData.empty()) {
                PROF_LOGE("paresd json object is empty, config path: %s", strConfigPath.c_str());
                return jsonData;
            }
            return jsonData;
        } else {
            PROF_LOGE("PROF_CONFIG_PATH : %s is empty or Permission Denied", strConfigPath.c_str());
            return jsonData;
        }
    }

    bool ServiceProfilerManager::ReadEnable(const json &config)
    {
        if (config.contains("enable")) {
            enable_ = config["enable"] == 1;
            return true;
        } else {
            return false;
        }
    }

    bool ServiceProfilerManager::ReadProfPath(const json &config)
    {
        if (config.contains("prof_dir")) {
            profPath_ = config["prof_dir"];
            if (profPath_.back() != '/') {
                profPath_.append("/");
            }
            return true;
        } else {
            return false;
        }
    }

    bool ServiceProfilerManager::ReadLevel(const json &config)
    {
        static const std::map<std::string, Level> enumMap = {
            {"ERROR", Level::ERROR},
            {"INFO", Level::INFO},
            {"DETAILED", Level::DETAILED},
            {"VERBOSE", Level::VERBOSE},
        };

        if (config.contains("profiler_level")) {
            try {
                level_ = Str2Uint(config["profiler_level"]);
            } catch (const std::invalid_argument &e) {
                PROF_LOGE("fail to convert profiler_level config to uint, will use default DETAILED");
            }
            if (level_ == 0) {
                std::string valueUpper = config["profiler_level"];
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

    void ServiceProfilerManager::LaunchThread()
    {
        auto t = std::thread(&ServiceProfilerManager::ThreadFunction, this);
        t.detach();
    }
    
    bool ServiceProfilerManager::ReadCollectConfig(const json &config)
    {
        bool retHost = ReadHostConfig(config);
        bool retNpu = ReadNpuConfig(config);
        return retHost && retNpu;
    }

    bool ServiceProfilerManager::ReadHostConfig(const json &config)
    {
        bool ret = true;
        if (config.contains("host_system_usage_freq")) {
            try {
                uint32_t hostFreq = config["host_system_usage_freq"];
                if (hostFreq >= hostFreqMin_ && hostFreq <= hostFreqMax_) {
                    hostFreq_ = hostFreq;
                    hostCpuUsage_ = true;
                    hostMemoryUsage_ = true;
                } else {
                    PROF_LOGE(
                        "host_system_usage_freq must be between %d and %d, "
                        "will not collect host cpu or host memory usage.",
                        hostFreqMin_,
                        hostFreqMax_);
                    hostCpuUsage_ = false;
                    hostMemoryUsage_ = false;
                    ret = false;
                }
            } catch (const std::exception &e) {
                PROF_LOGE("fail to convert host_system_usage_freq config to uint,"
                        "will not collect host cpu or host memory usage.");
                hostCpuUsage_ = false;
                hostMemoryUsage_ = false;
                ret = false;
            }
        } else {
            ret = false;
        }
        return ret;
    }

    bool ServiceProfilerManager::ReadNpuConfig(const json &config)
    {
        bool ret = true;
        if (config.contains("npu_memory_usage_freq")) {
            try {
                uint32_t npuMemoryFreq = config["npu_memory_usage_freq"];
                if (npuMemoryFreq >= npuMemoryFreqMin_ && npuMemoryFreq <= npuMemoryFreqMax_) {
                    npuMemoryFreq_ = npuMemoryFreq;
                    npuMemoryUsage_ = true;
                } else {
                    PROF_LOGE(
                        "npu_memory_usage_freq must be between %d and %d, will not collect npu memory usage.",
                        npuMemoryFreqMin_,
                        npuMemoryFreqMax_);
                    npuMemoryUsage_ = false;
                    ret = false;
                }
            } catch (const std::exception &e) {
                PROF_LOGE("fail to convert npu_memory_usage_freq config to uint, will not collect npu memory usage.");
                npuMemoryUsage_ = false;
                ret = false;
            }
            npuMemorySleepMilliseconds_ = static_cast<uint32_t>(std::round(MILLISECONDS_IN_SECOND / npuMemoryFreq_));
        } else {
            ret = false;
        }
        return ret;
    }

    // Funtion that write info to tx
    void Write2Tx(const std::vector<int> &memoryInfo, const std::string metricName)
    {
        for (long unsigned int i = 0; i < memoryInfo.size(); i++) {
            msServiceProfiler::Profiler<msServiceProfiler::INFO>()
                .Domain("npu")
                .Metric(metricName.c_str(), memoryInfo[i])
                .MetricScope("device", i)
                .Launch();
        }
    }

    // Dynamic Control according to config file modification
    void ServiceProfilerManager::DynamicControl()
    {
        std::string strConfigPath = getenv("PROF_CONFIG_PATH") ? getenv("PROF_CONFIG_PATH") : "";
        if (strConfigPath.empty()) {
            return;
        }
        struct stat configFileStat;
        if (stat(strConfigPath.c_str(), &configFileStat) == 0) {
            if (configFileStat.st_mtime == lastUpdate_) {
                return;
            } else {
                lastUpdate_ = configFileStat.st_mtime;
            }
        } else {
            PROF_LOGE("fail to get stat of %s", strConfigPath.c_str());
            return;
        }

        auto configJson = ReadConfig();
        auto enable_from_config = configJson["enable"] == 1;
        if (enable_from_config == true and enable_ == false) {
            PROF_LOGD("Profiler Enabled...");
            ReadProfPath(configJson);
            time_t now = time(nullptr);
            tm *ltm = std::localtime(&now);
            profPath_.append(std::to_string(ltm->tm_mon + 1))
                    .append(std::to_string(ltm->tm_mday))
                    .append("-")
                    .append(std::to_string(ltm->tm_hour))
                    .append(std::to_string(ltm->tm_min))
                    .append("/");

            ReadEnable(configJson);
            ReadLevel(configJson);
            ReadCollectConfig(configJson);
            StartServerProfiler();
            PROF_LOGD("Profiler Enabled Successfully!");
        } else if (enable_from_config == false and enable_ == true) {
            PROF_LOGD("Profiler Disabled...");
            StopServerProfiler();
            PROF_LOGD("Profiler Disabled Successfully!");
        } else {
            PROF_LOGD("Profiler Not Changed.");
        }
    }

    // 线程函数：npu usage and dynamic monitor
    void ServiceProfilerManager::ThreadFunction()
    {
        msServiceProfiler::NpuMemoryUsage npuMemoryUsage = msServiceProfiler::NpuMemoryUsage();
        npuMemoryUsage.InitDcmiCardAndDevices();
        while (g_threadRunFlag) {
            // dynamic start_and_stop
            DynamicControl();

            std::vector<int> memoryUsed;
            std::vector<int> memoryUtiliza;
            try {
                if (enable_ && npuMemoryUsage_) {
                    int ret = npuMemoryUsage.GetByDcmi(memoryUsed, memoryUtiliza);
                    Write2Tx(memoryUsed, "usage");
                    Write2Tx(memoryUtiliza, "utiliza");
                }
            } catch (std::exception& e) {
                PROF_LOGD("get npu memory usage failed");
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(this->npuMemorySleepMilliseconds_));
        }
    }

    void ServiceProfilerManager::SetAclProfHostSysConfig()
    {
        std::string hostProfString = "";

        // 根据条件设置 hostProfString 的值
        if (hostCpuUsage_ && hostMemoryUsage_) {
            hostProfString = "cpu,mem";
        } else if (hostCpuUsage_) {
            hostProfString = "cpu";
        } else if (hostMemoryUsage_) {
            hostProfString = "mem";
        }

        aclprofSetConfig(ACL_PROF_HOST_SYS, hostProfString.c_str(), strlen(hostProfString.c_str()));
        aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE, hostProfString.c_str(), strlen(hostProfString.c_str()));
        aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE_FREQ,
            std::to_string(hostFreq_).c_str(),
            strlen(std::to_string(hostFreq_).c_str()));
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

        aclError ret = aclprofInit(profPath_.c_str(), profPath_.size());
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof init failed, ret = %d", ret);
            return;
        }

        auto config_ = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_NONE, nullptr, profSwitch);
        if (config_ == nullptr) {
            PROF_LOGE("acl prof create config failed.");
            enable_ = false;
            return;
        }
        configHandle_ = config_;

        if (ret == ACL_ERROR_NONE) {
            SetAclProfHostSysConfig();
        }

        PROF_LOGD("begin to start profiling");
        ret = aclprofStart(config_);
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof start failed, ret = %d", ret);
            enable_ = false;
            return;
        }

        // 设置标志位
        g_threadRunFlag = true;

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
