/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <sys/stat.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <unistd.h>
#include <semaphore.h>
#include <utime.h>
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
#include <csignal>

#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mstx/ms_tools_ext.h"
#include "securec.h"

#include "../include/msServiceProfiler/NpuMemoryUsage.h"
#include "../include/msServiceProfiler/Profiler.h"
#include "../include/msServiceProfiler/ServiceProfilerManager.h"


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

namespace {
constexpr int MAX_TX_MSG_LEN = 128;
constexpr int MAX_DEVICE_NUM = 128;
constexpr int STRING_TO_UINT_BASE = 10;
constexpr int MILLISECONDS_IN_SECOND = 1000;

// 全局标志位，用于控制线程退出
std::atomic<bool> g_threadRunFlag(true);
} // end of anonymous namespace

static void MarkEventLongAttr(const char *msg)
{
    auto spanHandle = StartSpan();
    MarkSpanAttr(msg, spanHandle);
}

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

void MarkEvent(const char *msg)
{
    if (strlen(msg) > MAX_TX_MSG_LEN) {
        MarkEventLongAttr(msg);
    } else {
        mstxMarkA(msg, nullptr);
    }
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
        ReadConfigPath();
        MarkFirstProcessAsMain();
        InitProfPathDateTail();
        auto configJson = ReadConfig();
        ReadEnable(configJson);
        ReadAclTaskTime(configJson);
        ReadProfPath(configJson);
        ReadLevel(configJson);
        ReadCollectConfig(configJson);

        if (enable_) {
            StartProfiler();
        }
        LaunchThread();
    }

    ServiceProfilerManager::~ServiceProfilerManager()
    {
        std::string &exitSemName = GetConfigPath();
        if (!exitSemName.empty()) {
            shm_unlink(ServiceProfilerManager::ToSemName(exitSemName).c_str());
        }
    }


    void ServiceProfilerManager::ReadConfigPath()
    {
        configPath_ = getenv("SERVICE_PROF_CONFIG_PATH") ? getenv("SERVICE_PROF_CONFIG_PATH") : "";
        if (configPath_.empty()) {
            configPath_ = getenv("PROF_CONFIG_PATH") ? getenv("PROF_CONFIG_PATH") : "";
            if (access(configPath_.c_str(), F_OK) != 0) {
                configPath_ = "";
            }
        }
    }


    Json ServiceProfilerManager::ReadConfig()
    {
        Json jsonData;
        if (configPath_.empty()) {
            return jsonData;
        }
        if (access(configPath_.c_str(), F_OK) != 0) {
            PROF_LOGE("SERVICE_PROF_CONFIG_PATH : %s is not file or Permission Denied", configPath_.c_str());
            return jsonData;
        }

        std::ifstream configFile; // 单独创建 std::ifstream 对象
        try {
            configFile.open(configPath_);
            if (!configFile.good()) {
                PROF_LOGE("fail to open: %s", configPath_.c_str());
                return jsonData;
            }
        } catch (const std::exception &e) {
            PROF_LOGE("fail to open config file: %s, error: %s",
                      configPath_.c_str(), e.what());
            return jsonData;
        }

        try {
            configFile >> jsonData; // 尝试解析 JSON 数据
        } catch (const std::exception &e) {
            PROF_LOGE("fail to parse file content as json object, config path: %s, error: %s",
                      configPath_.c_str(), e.what());
            configFile.close(); // 确保文件关闭
            return jsonData;
        }

        configFile.close(); // 成功解析后关闭文件
        if (jsonData.empty()) {
            PROF_LOGE("paresd json object is empty, config path: %s", configPath_.c_str());
            return jsonData;
        }
        return jsonData;
    }

    void ServiceProfilerManager::ReadEnable(const Json &config)
    {
        enable_ = false;  // Default to false
        if (config.contains("enable")) {
            if (config["enable"].is_number_integer()) {
                enable_ = config["enable"] == 1;
            } else {
                PROF_LOGW("enable value is not an integer, will set false.");
            }
        }
        PROF_LOGD("profile enable_: %s", enable_ ? "true" : "false");
    }

    void ServiceProfilerManager::ReadProfPath(const Json &config)
    {
        if (config.contains("prof_dir")) {
            profPath_ = config["prof_dir"];
            if (profPath_.back() != '/') {
                profPath_.append("/");
            }
        } else {
            std::string homePath = getenv("HOME") ? getenv("HOME") : "";
            profPath_.append(homePath).append("/.ms_server_profiler/");
        }

        profPath_.append(profPathDateTail_);
    }

    void ServiceProfilerManager::ReadAclTaskTime(const Json &config)
    {
        enableAclTaskTime_ = false;  // Default to false
        if (config.contains("acl_task_time")) {
            if (config["acl_task_time"].is_number_integer()) {
                enableAclTaskTime_ = config["acl_task_time"] == 1;
            } else {
                PROF_LOGW("Unknown acl_task_time type. acl_task_time disabled.");
            }
        }
        PROF_LOGD("profile enableAclTaskTime_: %s", enableAclTaskTime_ ? "true" : "false");
    }

    void ServiceProfilerManager::ReadLevel(const Json &config)
    {
        level_ = Level::INFO;
        static const std::map<std::string, Level> ENUM_MAP = {
            {"ERROR",    Level::ERROR},
            {"INFO",     Level::INFO},
            {"DETAILED", Level::DETAILED},
            {"VERBOSE",  Level::VERBOSE},
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
                if (ENUM_MAP.find(valueUpper) != ENUM_MAP.end()) {
                    level_ = ENUM_MAP.at(valueUpper);
                } else {
                    PROF_LOGW("Unknown profiler_level. Use the default profiler level.");
                }
            }
        }
    }

    std::string ServiceProfilerManager::ToSemName(const std::string &oriSemName)
    {
        std::string semName = "/";
        semName.append(oriSemName);
        std::replace(++semName.begin(), semName.end(), '/', '#');
        return std::move(semName);
    }

    void ServiceProfilerManager::MarkFirstProcessAsMain()
    {
        const size_t mmapSize = 1024; // 共享内存对象的大小
        const size_t infoMaxSize = 128; // 内存中信息的最大大小

        std::string &semNameTouchTime = GetConfigPath();

        if (semNameTouchTime.empty()) {
            return;
        }

        int shmFd = shm_open(ToSemName(semNameTouchTime).c_str(), O_CREAT | O_RDWR, 0666);
        if (shmFd == -1) {
            PROF_LOGW("shm_open failed");
            return;
        }

        // 设置共享内存对象的大小
        if (ftruncate(shmFd, mmapSize) == -1) {
            PROF_LOGW("ftruncate failed");
            close(shmFd);
            return;
        }

        // 将共享内存对象映射到进程地址空间
        void *mmapPtr = mmap(nullptr, mmapSize, PROT_READ | PROT_WRITE, MAP_SHARED, shmFd, 0);
        if (mmapPtr == MAP_FAILED) {
            PROF_LOGW("mmap failed");
            close(shmFd);
            return;
        }
        char *pInfoStr = static_cast<char *>(mmapPtr);
        std::string infoStr(pInfoStr, infoMaxSize);

        auto splitInfo = SplitStr(infoStr.c_str(), ',');  // 格式为： pid,目录。所以使用逗号分隔开
        if (!splitInfo.first.empty()) {
            pid_t pid = Str2Uint(splitInfo.first); // 检查的进程 PID, 如果存在，就将和它放到一个目录中
            if (kill(pid, 0) == 0) {
                isMaster_ = false;
                profPathDateTail_ = splitInfo.second;
                PROF_LOGD("is not Master");
            }
        }

        if (isMaster_) {
            std::string infoOut;
            InitProfPathDateTail(true);
            infoOut.append(std::to_string(getpid())).append(",").append(profPathDateTail_);
            if (sprintf_s(pInfoStr, infoMaxSize, "%s", infoOut.c_str()) == -1) {
                PROF_LOGW("cannot write to mmap");
            }
        }
        close(shmFd);
    }

    void ServiceProfilerManager::InitProfPathDateTail(bool forceReinit)
    {
        const size_t tailMaxSize = 32; // 目录的最大大小

        if (profPathDateTail_.empty() || forceReinit) {
            time_t now = time(nullptr);
            auto ltm = std::localtime(&now);
            char pStrDateTail[tailMaxSize + 1] = {0};  // 多申请一点，保证安全
            sprintf_s(pStrDateTail, tailMaxSize, "%02d%02d-%02d%02d/",
                      ltm->tm_mon + 1, ltm->tm_mday, ltm->tm_hour, ltm->tm_min);
            profPathDateTail_ = pStrDateTail;
        }
    }

    void ServiceProfilerManager::LaunchThread()
    {
        auto t = std::thread(&ServiceProfilerManager::ThreadFunction, this);
        t.detach();
    }

    bool ServiceProfilerManager::ReadCollectConfig(const Json &config)
    {
        bool retHost = ReadHostConfig(config);
        bool retNpu = ReadNpuConfig(config);
        return retHost && retNpu;
    }

    bool ServiceProfilerManager::ReadHostConfig(const Json &config)
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
                        "host_system_usage_freq must be between %u and %u, "
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

    bool ServiceProfilerManager::ReadNpuConfig(const Json &config)
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
                            "npu_memory_usage_freq must be between %u and %u, will not collect npu memory usage.",
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
        if (configPath_.empty()) {
            return;
        }
        struct stat configFileStat;
        if (stat(configPath_.c_str(), &configFileStat) == 0) {
            if (configFileStat.st_mtime == lastUpdate_) {
                return;
            } else {
                lastUpdate_ = configFileStat.st_mtime;
            }
        } else {
            PROF_LOGE("fail to get stat of %s", configPath_.c_str());
            return;
        }

        auto configJson = ReadConfig();
        auto enableFromConfig = configJson["enable"] == 1;
        if (enableFromConfig && !enable_) {
            PROF_LOGD("Profiler Enabled...");
            ReadEnable(configJson);
            ReadLevel(configJson);
            ReadProfPath(configJson);
            ReadAclTaskTime(configJson);
            ReadCollectConfig(configJson);
            StartServerProfiler();
            PROF_LOGD("Profiler Enabled Successfully!");
        } else if (!enableFromConfig && enable_) {
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
                if (enable_ && npuMemoryUsage_ && isMaster_
                    && npuMemoryUsage.GetByDcmi(memoryUsed, memoryUtiliza) == EXITCODE_SUCCESS) {
                    Write2Tx(memoryUsed, "usage");
                    Write2Tx(memoryUtiliza, "utiliza");
                }
            } catch (std::exception &e) {
                PROF_LOGD("get npu memory usage failed");
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(this->npuMemorySleepMilliseconds_));
        }
    }

    void ServiceProfilerManager::SetAclProfHostSysConfig() const
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

        if (!isAclInit_) {
            aclError retInit = aclInit(nullptr);
            if (retInit == ACL_SUCCESS || retInit == ACL_ERROR_REPEAT_INITIALIZE) {
                isAclInit_ = true;
            } else {
                PROF_LOGE("acl init failed, ret = %d", retInit);
                isAclInit_ = false;
            }
        }

        aclError ret = aclprofInit(profPath_.c_str(), profPath_.size());
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof init failed, ret = %d", ret);
            return;
        }

        auto profConfig = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_NONE, nullptr, profSwitch);
        if (profConfig == nullptr) {
            PROF_LOGE("acl prof create config failed.");
            enable_ = false;
            return;
        }
        this->configHandle_ = profConfig;

        if (ret == ACL_ERROR_NONE && isMaster_) {
            SetAclProfHostSysConfig();
        }

        PROF_LOGD("begin to start profiling");
        ret = aclprofStart(profConfig);
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

        auto profConfig = (aclprofConfig *)this->configHandle_;

        auto ret = aclprofStop(profConfig);
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof stop failed, ret = %d", ret);
            return;
        }
        ret = aclprofDestroyConfig(profConfig);
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof destroy config failed, ret = %d", ret);
            return;
        }
        this->configHandle_ = nullptr;

        ret = aclprofFinalize();
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof finalize failed, ret = %d", ret);
            return;
        }

        started_ = false;
    }
}  // namespace msServiceProfiler
