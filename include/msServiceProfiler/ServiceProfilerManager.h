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

#ifndef MS_SERVER_PROFILER_MARKER_H
#define MS_SERVER_PROFILER_MARKER_H

#include <string>
#include <thread>
#include <atomic>
#include <limits>

#include <nlohmann/json.hpp>

#include "ServiceProfilerInterface.h"
#include "Config.h"
#include "NpuMemoryUsage.h"

#include "acl/acl.h"
#include "mspti/mspti.h"

using Json = nlohmann::json;

namespace msServiceProfiler {
    constexpr uint32_t INVALID_DEVICE_ID = std::numeric_limits<uint32_t>::max();
    using AclprofConfig = struct aclprofConfig;
    class ServiceProfilerManager {
    public:
        ServiceProfilerManager(const ServiceProfilerManager &) = delete;
        ServiceProfilerManager& operator=(const ServiceProfilerManager &) = delete;

        static ServiceProfilerManager &GetInstance();

        inline bool IsEnable(uint32_t level) const
        {
            return config_->GetEnable() && config_->GetLevel() >= level;
        }

        inline bool GetEnableDomainFilter() const { return config_->GetEnableDomainFilter(); }

        const std::set<std::string>& GetValidDomain() const { return config_->GetValidDomain(); }

        void NotifyStartProfiler()
        {
            notifyStarted = true;
        }

        void NotifyStopProfiler()
        {
            notifyStarted = false;
        }

        void StartProfiler(bool isInit = false);

        void StartAclProfiler(const std::string& profPath, uint32_t deviceID);

        void StopProfiler();

        void NotifyDeviceID(uint32_t deviceID);

        void StopThread();

        static std::string ToSemName(const std::string &oriSemName);

        const std::string &GetConfigPath()
        {
            return config_->GetConfigPath();
        }

        const std::string &GetProfPath() const
        {
            return config_->GetProfPath();
        }

    private:
        ServiceProfilerManager();

        ~ServiceProfilerManager();

        void SetAclProfHostSysConfig() const;

        void DynamicControl();

        void LaunchThread();

        void ThreadFunction();

        void MarkFirstProcessAsMain();

        AclprofConfig* ProfCreateConfig(uint32_t deviceID);

        void StartMsptiProf(const std::string& profPath);

        void StartAclProf(const std::string& profPath, uint32_t deviceID);

        void StopAclProf();

        void RecordMemoryUsage(NpuMemoryUsage& npuMemoryUsage);

        void ProfTimerCtrl();

    private:
        bool isMaster_ = true;  // 构造时初始化一次，在工作线程启动前，不涉及多个线程修改
        bool started_ = false;  // 整体启动状态，构造时可能会初始化一次，在工作线程启动前；其他修改都在工作进程中，不涉及多个线程修改
        bool aclProfStarted_ = false;  // aclprof 启动状态。生命周期同上
        bool msptiStarted_ = false;  // mspti 启动状态。生命周期同上
        void *configHandle_ = nullptr;  // aclprof 保存一个配置的指针，在销毁的时候需要。生命周期同上
        msptiSubscriberHandle msptiHandle_; // mspti 保存一个的指针，在销毁的时候需要。生命周期同上

        int lastUpdate_ = 0;    // 记录文件修改时间，仅在工作线程中使用，不涉及多个线程修改
        std::chrono::high_resolution_clock::time_point initiate = std::chrono::high_resolution_clock::now();  // 开始的时间，用于自动关闭控制，工作线程启动前可能初始化一次；其他修改都在工作进程中，不涉及多个线程修改
        std::atomic<bool> threadRunFlag_{true}; // 多线程使用，原子的，多线程安全，不是原子也没啥关系，只有用户线程会改，工作线程只会读取
        std::atomic<bool> notifyStarted{false}; // 多线程使用，原子的，多线程安全，当它和 started 不一样的时候，工作线程会调用开启或关闭prof动作
        std::atomic<uint32_t> deviceID_ {INVALID_DEVICE_ID}; // 当前进程的 device id

        std::thread thread_; // 我就是线程

        // config_ 为了速度，目前不加锁，所以多线程存在风险
        // 生命周期：在构造的时候初始化一次，其余在工作线程中变化，用户线程只会读取。
        // 部分风险消减方案
        // 1. 不过一般不太会修改。只有用户改配置文件才会变更
        // 2. enable 和 level 是变化是类似原子的。读取可能会乱，但是不影响，判断错误就算了，没关系
        // 3. 其他变量，只有在 enable 变化的时候才可能会变化
        //    3.1 enable 从 true 变为 false ，变量不会变，无风险
        //    3.2 enable 从 false 变为 true ，变量会变化，但是采集一般都先判断 enable 等于 true 才会继续执行其他。在变化的时候，优先变化其他变量，最后修改 enable
        //
        // 其实还是存在极其小的风险。如果出现，一般是偶现问题。目前还没发现这个原因导致的问题。
        std::shared_ptr<Config> config_;
    };
}  // namespace msServiceProfiler

#endif
