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

#ifndef MS_SERVICE_PROFILER_SERVICETRACER_H
#define MS_SERVICE_PROFILER_SERVICETRACER_H

#include <iostream>
#include <fstream>
#include <sys/un.h>
#include "Utils.h"
#include "MultiThreadBufferManager.h"

namespace msServiceProfiler {
class TraceSender {
public:
    TraceSender(std::string &&strMsg) : msg_(std::move(strMsg))
    {}

    void Execute();

private:
    std::string msg_;
};

class ServiceTracerSender {
public:
    explicit ServiceTracerSender()
        : bufferManger_{std::bind(&ServiceTracerSender::RecvDbExecutor, this, std::placeholders::_1),
              std::bind(&ServiceTracerSender::ExecutorDumpToDb, this)} {};

    static ServiceTracerSender &GetSender()
    {
        static ServiceTracerSender manager;
        return manager;
    };

    std::shared_ptr<DbBuffer<TraceSender>> Register(uintptr_t pThreadIns)
    {
        return bufferManger_.Register(pThreadIns);
    }

    void Unregister(uintptr_t pThreadIns)
    {
        bufferManger_.Unregister(pThreadIns);
    }

private:
    void RecvDbExecutor(std::unique_ptr<TraceSender> dbExecutor)
    {
        dbExecutor->Execute();
    }

    void ExecutorDumpToDb()
    {
        // 可以先保存，组Batch再发送
    }

private:
    MultiThreadBufferManager<TraceSender> bufferManger_;  // 优先析构，析构会停止内部 thread
};

class ServiceTraceThreadSender {
public:
    ServiceTraceThreadSender()
    {
        pBuffer = ServiceTracerSender::GetSender().Register(reinterpret_cast<uintptr_t>(this));
    }

    ~ServiceTraceThreadSender()
    {
        ServiceTracerSender::GetSender().Unregister(reinterpret_cast<uintptr_t>(this));
    }

    inline static ServiceTraceThreadSender &GetSender()
    {
        thread_local ServiceTraceThreadSender sender;
        return sender;
    }

    void Send(std::unique_ptr<TraceSender> activity)
    {
        if (pBuffer) {
            auto pRetData = pBuffer->Push(std::move(activity));
        }
    }

private:
    std::shared_ptr<DbBuffer<TraceSender>> pBuffer = nullptr;
};

void SendTracer(std::string &&traceMsg);

class UnixSocketSender {
public:
    explicit UnixSocketSender(const std::string& abstract_socket_name);
    bool Connect();
    bool Send(const std::string& data);
    std::string GetErrorMsg() const { return errorMsg_; }
    bool IsConnected() const { return isConnected_; }

    ~UnixSocketSender();

private:
    int sockfd_;
    struct sockaddr_un addr_;
    std::string errorMsg_;
    bool isConnected_;
};

}  // namespace msServiceProfiler

#endif  // MS_SERVICE_PROFILER_SERVICETRACER_H
