/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <semaphore.h>
#include <time.h>
#include <fcntl.h>

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
#include <sys/utime.h>

#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mstx/ms_tools_ext.h"

#include "../include/msServiceProfiler/NpuMemoryUsage.h"
#include "../include/msServiceProfiler/Profiler.h"
#include "../include/msServiceProfiler/ServiceProfilerManager.h"


constexpr int MAX_TX_MSG_LEN = 128;
constexpr int MAX_DEVICE_NUM = 128;
constexpr int STRING_TO_UINT_BASE = 10;

// 全局标志位，用于控制线程退出
std::atomic<bool> g_threadRunFlag(true);

#define PROF_LOGD(...)       \
    do {                     \
        printf(__VA_ARGS__); \
        printf("\n");        \
    } while (0)

#define PROF_LOGW(...)       \
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
        ReadConfigPath();
        MarkFirstProcessAsMain();
        TouchConfigPath();
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


    void ServiceProfilerManager::ReadConfigPath() {
        configPath_ = getenv("SERVICE_PROF_CONFIG_PATH") ? getenv("SERVICE_PROF_CONFIG_PATH") : "";
        if (configPath_.empty()) {
            configPath_ = getenv("PROF_CONFIG_PATH") ? getenv("PROF_CONFIG_PATH") : "";
        }
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

    void ServiceProfilerManager::ReadEnable(const json &config)
    {
        if (config.contains("enable")) {
            enable_ = config["enable"] == 1;
        } else {
            enable_ = false;
        }
    }

    void ServiceProfilerManager::ReadProfPath(const json &config)
    {
        if (config.contains("prof_dir")) {
            profPath_ = config["prof_dir"];
            if (profPath_.back() != '/') {
                profPath_.append("/");
            }
        }
    }

    void ServiceProfilerManager::ReadAclTaskTime(const json &config)
    {
        if (config.contains("acl_task_time") ) {
            if (config["acl_task_time"].is_number_integer()) {
                enableAclTaskTime_ = config["acl_task_time"] == 1;
                return;
            } else {
                PROF_LOGW("Unknown acl_task_time type. acl_task_time disabled.");
            }
        }
        enableAclTaskTime_ = false;
    }

    void ServiceProfilerManager::ReadLevel(const json &config)
    {
        level_ = Level::INFO;
        static const std::map<std::string, Level> enumMap = {
            {"ERROR", Level::ERROR},
            {"INFO", Level::INFO},
            {"DETAILED", Level::DETAILED},
            {"VERBOSE", Level::VERBOSE},
        };

        if (config.contains("profiler_level")) {
            const auto profilerLevel = config["profiler_level"];
            if (profilerLevel.is_number_integer()) {
                int level = profilerLevel.get<int>();
                if (level >= 0) {
                    level_ = level;
                }
            } else if (profilerLevel.is_string()) {
                std::string valueUpper = profilerLevel;
                std::transform(valueUpper.begin(), valueUpper.end(), valueUpper.begin(), [](char const &c) {
                    return std::toupper(c);
                });
                if (enumMap.find(valueUpper) != enumMap.end()) {
                    level_ = enumMap.at(valueUpper);
                } else {
                    PROF_LOGW("Unknown profiler_level. Use the default profiler level.");
                }
            }
            return true;
        } else {
            return false;
        }
    }



    void ServiceProfilerManager::MarkFirstProcessAsMain()
    {
        std::string& semNameTouchTime = msServiceProfiler::ServiceProfilerManager::GetInstance().GetConfigPath();
        sem_t* semaphore = sem_open(semNameTouchTime.c_str(), O_CREAT, 0600, 1);
        if (semaphore == SEM_FAILED) {
            return;
        }

        if (sem_trywait(semaphore) == -1) {
            isMaster = false;
        }
        sem_close(semaphore);
        // 在程序退出时删除信号量
        std::atexit([]() {
            sem_unlink(msServiceProfiler::ServiceProfilerManager::GetInstance().GetConfigPath().c_str());
        });
    }

    void ServiceProfilerManager::TouchConfigPath()
    {
        std::string& semNameTouchTime = msServiceProfiler::ServiceProfilerManager::GetInstance().GetConfigPath();
        std::string semNameWaitTime = semNameTouchTime + "Wait";
        if (isMaster) {
            // mod config file
            struct utimbuf new_times{};
            new_times.actime = time(nullptr);      // set as now
            new_times.modtime = time(nullptr);     // set as now

            if (utime(configPath_.c_str(), &new_times) != 0) {
                PROF_LOGW("change config file mod time failed");
            }
            sem_t* semaphore_wait = sem_open(semNameWaitTime.c_str(), O_CREAT, 0600, 10000);
            if (semaphore_wait != SEM_FAILED) {
                sem_close(semaphore_wait);
            }
            std::atexit([]() {
                std::string & semName = msServiceProfiler::ServiceProfilerManager::GetInstance().GetConfigPath();
                std::string exitSemNameWaitTime = semName + "Wait";
                sem_unlink(exitSemNameWaitTime.c_str());
            });
        } else {
            sem_t* semaphore_wait = sem_open(semNameWaitTime.c_str(), _O_RDONLY);
            if (semaphore_wait != SEM_FAILED) {
                // 等 Master touch 配置文件，最多等一秒钟
                struct timespec ts;
                clock_gettime(CLOCK_REALTIME, &ts);
                ts.tv_sec += 1;
                if (sem_timedwait(semaphore_wait, &ts) == -1) {
                    PROF_LOGW("wait semaphore failed");
                }
                sem_close(semaphore_wait);
            }
        }
    }

    void ServiceProfilerManager::AppendProfPathTailByConfigFile()
    {
        tm *ltm = nullptr;
        if (!configPath_.empty() && access(configPath_.c_str(), F_OK) == 0) {
            struct stat attr;
            if (stat(configPath_.c_str(), &attr) == 0) {
                ltm = std::localtime(&attr.st_mtime);
            }
        }
        if (ltm == nullptr) {
            time_t now = time(nullptr);
            ltm = std::localtime(&now);
        }

        profPath_.append(std::to_string(ltm->tm_mon + 1))
                .append(std::to_string(ltm->tm_mday))
                .append("-")
                .append(std::to_string(ltm->tm_hour))
                .append(std::to_string(ltm->tm_min))
                .append("/");
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
                    if (ret == EXITCODE_SUCCESS) {
                        Write2Tx(memoryUsed, "usage");
                        Write2Tx(memoryUtiliza, "utiliza");
                    }
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

        uint32_t profSwitch = ACL_PROF_MSPROFTX;
        if (enableAclTaskTime_) {
            profSwitch |= ACL_PROF_TASK_TIME_L0;
        }
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
