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
#include <climits>
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

#include "msServiceProfiler/NpuMemoryUsage.h"
#include "msServiceProfiler/Profiler.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceProfilerManager.h"
#include "msServiceProfiler/ServiceProfilerMspti.h"

namespace {
constexpr int MAX_TX_MSG_LEN = 128;
constexpr int MAX_DEVICE_NUM = 128;
constexpr int STRING_TO_UINT_BASE = 10;
constexpr uint32_t INVALID_DEVICE_ID = static_cast<uint32_t>(-1);

using DATA_PTR = struct ProfSetDevPara *;

struct ProfSetDevPara {
    uint32_t chipId;
    uint32_t deviceId;
    bool isOpen;
};

std::unordered_map<int, struct sigaction> old_handlers; // 储存旧有信号处理函数

// 全局标志位，用于控制线程退出
std::atomic<bool> g_threadRunFlag(true);
uint32_t g_deviceID = INVALID_DEVICE_ID;
bool g_startFlag = false;
} // end of anonymous namespace

static void MarkEventLongAttr(const char *msg)
{
    if (msg == nullptr) {
        return;
    }
    auto spanHandle = StartSpan();
    MarkSpanAttr(msg, spanHandle);
}

SpanHandle StartSpan()
{
    return mstxRangeStartA("", nullptr);
}

SpanHandle StartSpanWithName(const char *name)
{
    if (name == nullptr) {
        return StartSpan();
    }

    return mstxRangeStartA(name, nullptr);
}

void MarkSpanAttr(const char *msg, SpanHandle spanHandle)
{
    if (msg == nullptr) {
        return;
    }

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
        auto markSize = std::min(maxMarkSize, msgLen); // prevent out-of-bounds accessing
        spanTag.append(oriMsgStart, markSize);
        oriMsgStart += markSize;
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
    if (msg == nullptr) {
        return;
    }

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

void MsprofSetDeviceCallbackImpl(DATA_PTR data, uint32_t len)
{
    if (len != sizeof(::ProfSetDevPara)) {
        return;
    }
    if (data == nullptr) {
        return;
    }
    DATA_PTR setCfg = static_cast<DATA_PTR>(data);
    if (setCfg->deviceId != g_deviceID && g_startFlag) {
        g_deviceID = setCfg->deviceId;
        StopServerProfiler();
        StartServerProfiler();
    } else {
        g_deviceID = setCfg->deviceId;
    }
    return;
}

void RegisterSetDeviceCallback()
{
    void *handle = dlopen("libprofapi.so", RTLD_LAZY | RTLD_LOCAL);
    if (handle == nullptr) {
        PROF_LOGW("Failed to dlopen libprofapi.so. Will be not able to get device profiling data. "
            "Check whether a NPU server or if cann toolkit installed.");
        return;
    }

    using ProfSetDeviceHandle = void (*)(DATA_PTR, uint32_t);
    using ProfRegDeviceStateCallbackFunc = int32_t (*)(ProfSetDeviceHandle);
    ProfRegDeviceStateCallbackFunc profRegDeviceStateCallback =
        (ProfRegDeviceStateCallbackFunc)(dlsym(handle, "profRegDeviceStateCallback"));

    profRegDeviceStateCallback(MsprofSetDeviceCallbackImpl);
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
            return {str, ""};
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
        : configHandle_(nullptr), config_(std::unique_ptr<Config>(new Config()))
    {
        ProfLogInit();
        MarkFirstProcessAsMain();

        RegisterSetDeviceCallback();
        if (config_->GetEnable()) {
            StartProfiler();
        }
        LaunchThread();

        // 注册中断终止信号处理函数
        RegisterSignal(SIGINT);
        RegisterSignal(SIGTERM);
    }

    ServiceProfilerManager::~ServiceProfilerManager()
    {
        StopThread();
    }

    void ServiceProfilerManager::StopThread()
    {
        const std::string &exitSemName = GetConfigPath();
        if (!exitSemName.empty()) {
            shm_unlink(ServiceProfilerManager::ToSemName(exitSemName).c_str());
        }

        if (this->thread_.joinable()) {
            g_threadRunFlag = false;
            this->thread_.join();
        }
    }

    std::string ServiceProfilerManager::ToSemName(const std::string &oriSemName)
    {
        std::string semName = "/";
        semName.append(oriSemName);
        std::replace(++semName.begin(), semName.end(), '/', '#');
        return semName;
    }

    void ServiceProfilerManager::MarkFirstProcessAsMain()
    {
        const size_t mmapSize = 1024; // 共享内存对象的大小
        const size_t infoMaxSize = 1000; // 内存中信息的最大大小

        const std::string &semNameTouchTime = config_->GetConfigPath();

        if (semNameTouchTime.empty()) {
            return;
        }

        int shmFd = shm_open(ToSemName(semNameTouchTime).c_str(), O_CREAT | O_RDWR, 0666);
        if (shmFd == -1) {
            PROF_LOGW("shm_open failed");  // LCOV_EXCL_LINE
            return;
        }

        // 设置共享内存对象的大小
        if (ftruncate(shmFd, mmapSize) == -1) {
            PROF_LOGW("ftruncate failed");  // LCOV_EXCL_LINE
            close(shmFd);
            return;
        }

        // 将共享内存对象映射到进程地址空间
        void *mmapPtr = mmap(nullptr, mmapSize, PROT_READ | PROT_WRITE, MAP_SHARED, shmFd, 0);
        if (mmapPtr == MAP_FAILED) {
            PROF_LOGW("mmap failed");  // LCOV_EXCL_LINE
            close(shmFd);
            return;
        }
        char *pInfoStr = static_cast<char *>(mmapPtr);
        std::string infoStr(pInfoStr, infoMaxSize);

        auto splitInfo = SplitStr(infoStr, ',');  // 格式为： pid,目录。所以使用逗号分隔开
        if (!splitInfo.second.empty()) {
            pid_t pid = static_cast<pid_t>(Str2Uint(splitInfo.first)); // 检查的进程 PID, 如果存在，就将和它放到一个目录中
            if (kill(pid, 0) == 0) {
                isMaster_ = false;
                config_->SetProfPathDateTail(std::string(splitInfo.second.c_str()));
            }
        }

        if (isMaster_) {
            std::string infoOut;
            config_->InitProfPathDateTail(true);
            infoOut.append(std::to_string(getpid())).append(",").append(config_->GetProfPathDateTail());
            if (sprintf_s(pInfoStr, infoMaxSize, "%s", infoOut.c_str()) == -1) {
                PROF_LOGW("cannot write to mmap");  // LCOV_EXCL_LINE
            }
        }
        close(shmFd);
    }

    void ServiceProfilerManager::LaunchThread()
    {
        this->thread_ = std::thread(&ServiceProfilerManager::ThreadFunction, this);
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
        auto configPath = config_->GetConfigPath();
        if (configPath.empty()) {
            return;
        }
        struct stat configFileStat;
        if (stat(configPath.c_str(), &configFileStat) == 0) {
            if (configFileStat.st_mtime == lastUpdate_) {
                return;
            } else {
                lastUpdate_ = configFileStat.st_mtime;
            }
        } else {
            LOG_ONCE_E("fail to get stat of %s", configPath.c_str());  // LCOV_EXCL_LINE
            return;
        }

        auto configJson = config_->ReadConfigFile();
        auto enableFromConfig = configJson["enable"] == 1;
        if (enableFromConfig && !config_->GetEnable()) {
            PROF_LOGI("Profiler Enabled...");  // LCOV_EXCL_LINE
            config_->ParseConfig(configJson);
            StartServerProfiler();
            PROF_LOGI("Profiler Enabled Successfully!");  // LCOV_EXCL_LINE
        } else if (!enableFromConfig && config_->GetEnable()) {
            PROF_LOGI("Profiler Disabled...");  // LCOV_EXCL_LINE
            StopServerProfiler();
            PROF_LOGI("Profiler Disabled Successfully!");  // LCOV_EXCL_LINE
        }
    }

    // 线程函数：npu usage and dynamic monitor
    void ServiceProfilerManager::ThreadFunction()
    {
        msServiceProfiler::NpuMemoryUsage npuMemoryUsage = msServiceProfiler::NpuMemoryUsage();
        int ret = npuMemoryUsage.InitDcmiCardAndDevices();
        if (ret != EXITCODE_SUCCESS) {
            PROF_LOGE(
                "InitDcmiCardAndDevices failed. Check whether a NPU server "
                "or if NPU driver installed.");  // LCOV_EXCL_LINE
            return;
        }

        while (g_threadRunFlag) {
            // dynamic start_and_stop
            DynamicControl();

            std::vector<int> memoryUsed;
            std::vector<int> memoryUtiliza;
            try {
                if (config_->GetEnable() && config_->GetNpuMemoryUsage() && isMaster_
                    && npuMemoryUsage.GetByDcmi(memoryUsed, memoryUtiliza) == EXITCODE_SUCCESS) {
                    Write2Tx(memoryUsed, "usage");
                    Write2Tx(memoryUtiliza, "utiliza");
                }
            } catch (std::exception &e) {
                PROF_LOGD("get npu memory usage failed");  // LCOV_EXCL_LINE
            }
            
            if (msptiEnabled) {
                FlushBufferByTime();
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(config_->GetNpuMemorySleepMilliseconds()));
        }
    }

    void ServiceProfilerManager::SetAclProfHostSysConfig() const
    {
        std::string hostProfString = "";

        // 根据条件设置 hostProfString 的值
        if (config_->GetHostCpuUsage() && config_->GetHostMemoryUsage()) {
            hostProfString = "cpu,mem";
        } else if (config_->GetHostCpuUsage()) {
            hostProfString = "cpu";
        } else if (config_->GetHostMemoryUsage()) {
            hostProfString = "mem";
        }

        aclprofSetConfig(ACL_PROF_HOST_SYS, hostProfString.c_str(), strlen(hostProfString.c_str()));
        aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE, hostProfString.c_str(), strlen(hostProfString.c_str()));
        aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE_FREQ,
                         std::to_string(config_->GetHostFreq()).c_str(),
                         strlen(std::to_string(config_->GetHostFreq()).c_str()));
    }

    AclprofConfig* ServiceProfilerManager::ProfCreateConfig()
    {
        uint32_t profSwitch = ACL_PROF_MSPROFTX;

        uint32_t deviceIdList[MAX_DEVICE_NUM] = {0};
        uint32_t deviceNums = 1;
        if (g_deviceID == INVALID_DEVICE_ID) {
            deviceNums = 0;  // On host process
        } else {
            deviceNums = 1;  // On device process
            deviceIdList[0] = g_deviceID;
            if (config_->GetEnableAclTaskTime()) {
                profSwitch |= ACL_PROF_TASK_TIME_L0;
            }
        }

        auto profConfig = aclprofCreateConfig(deviceIdList, deviceNums, ACL_AICORE_NONE, nullptr, profSwitch);
        if (profConfig == nullptr) {
            PROF_LOGE("acl prof create config failed.");  // LCOV_EXCL_LINE
        } else {
            this->configHandle_ = profConfig;
        }
        return profConfig;
    }

    void ServiceProfilerManager::StartProfiler()
    {
        if (started_) {
            return;
        }

        auto profPath = config_->GetProfPath();
        if (!MakeDirs(profPath)) {
            PROF_LOGE("create path(%s) failed", profPath.c_str());  // LCOV_EXCL_LINE
        }
        PROF_LOGI("prof path: %s", profPath.c_str());  // LCOV_EXCL_LINE

        if (config_->GetEnableMspti()) {
            StartMsptiProf(profPath);
            }
        } else {
            StartAclProf(profPath);
        }
    }

    void ServiceProfilerManager::StartMsptiProf(std::string profPath)
    {
        auto ret = InitMspti(profPath, msptiHandle_);
        if (ret != 0 ) {
            PROF_LOGE("Mspti init failed.");
            msptiEnabled = false;
        } else {
            InitMsptiActivity(
                config_->GetEnableMspti()
                );
            auto apiFilter_ = config_->GetApiFilter();
            auto kernelFilter_ = config_->GetKernelFilter();
            auto hcclFilter_ = config_->GetHcclFilter();
            InitMsptiFilter(apiFilter_, kernelFilter_, hcclFilter_);
            msptiEnabled = true;

        // 设置标志位
        config_->SetEnable(true);
        g_threadRunFlag = true;
        started_ = true;
        g_startFlag = true;
    }

    void ServiceProfilerManager::StartAclProf(std::string profPath)
    {
        if (!isAclInit_) {
            aclError retInit = aclInit(nullptr);
            if (retInit == ACL_SUCCESS || retInit == ACL_ERROR_REPEAT_INITIALIZE) {
                isAclInit_ = true;
            } else {
                PROF_LOGE("acl init failed, ret = %d", retInit);  // LCOV_EXCL_LINE
                isAclInit_ = false;
            }
        }

        aclError ret = aclprofInit(profPath.c_str(), profPath.size());
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof init failed, ret = %d", ret);  // LCOV_EXCL_LINE
            return;
        }

        if (ret == ACL_ERROR_NONE && isMaster_) {
            SetAclProfHostSysConfig();
        }

        auto profConfig = ProfCreateConfig();
        if (profConfig == nullptr) {
            config_->SetEnable(false);
            return;
        }

        PROF_LOGD("begin to start profiling, device_id: %d", g_deviceID);  // LCOV_EXCL_LINE
        ret = aclprofStart(profConfig);
        if (ret != ACL_ERROR_NONE) {
            PROF_LOGE("acl prof start failed, ret = %d", ret);  // LCOV_EXCL_LINE
            config_->SetEnable(false);
            return;
        }

        // 设置标志位
        config_->SetEnable(true);
        g_threadRunFlag = true;
        started_ = true;
        g_startFlag = true;
    }

    void ServiceProfilerManager::StopProfiler()
    {
        if (!started_) {
            return;
        }

        config_->SetEnable(false);
        auto profConfig = (AclprofConfig *)this->configHandle_;

        if (msptiEnabled) {
            msptiEnabled = false;
            UninitMspti(msptiHandle_);
        } else {
            auto ret = aclprofStop(profConfig);
            if (ret != ACL_ERROR_NONE) {
                PROF_LOGE("acl prof stop failed, ret = %d", ret);  // LCOV_EXCL_LINE
                return;
            }
            ret = aclprofDestroyConfig(profConfig);
            if (ret != ACL_ERROR_NONE) {
                PROF_LOGE("acl prof destroy config failed, ret = %d", ret);  // LCOV_EXCL_LINE
                return;
            }
            this->configHandle_ = nullptr;

            ret = aclprofFinalize();
            if (ret != ACL_ERROR_NONE) {
                PROF_LOGE("acl prof finalize failed, ret = %d", ret);  // LCOV_EXCL_LINE
                return;
            }
        }

        started_ = false;
        g_startFlag = false;
    }
}  // namespace msServiceProfiler
