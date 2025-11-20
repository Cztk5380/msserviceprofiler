/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef MS_SERVICE_PROFILER_SERVICETRACER_H
#define MS_SERVICE_PROFILER_SERVICETRACER_H

#include <iostream>
#include <fstream>
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

}  // namespace msServiceProfiler

#endif  // MS_SERVICE_PROFILER_SERVICETRACER_H
