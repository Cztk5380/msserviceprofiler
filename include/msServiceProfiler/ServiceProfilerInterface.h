// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.

#ifndef MS_SERVER_PROFILER_INTERFACE_H
#define MS_SERVER_PROFILER_INTERFACE_H

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <set>
#include <string>
#include <cstdlib>
#include <sys/stat.h>
#include <linux/limits.h>

using SpanHandle = uint64_t;

#define MS_SERVICE_PROFILER_API __attribute__((visibility("default")))
#define MS_SERVICE_PROFILER_HIDDEN __attribute__((visibility("hidden")))
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
#define MS_SERVICE_INLINE_FLAG [[gnu::noinline]]
#else
#define MS_SERVICE_INLINE_FLAG inline
#endif

extern "C" {
/**
    * @brief 记录一个性能监测区间（Span）的开始节点
    * @return 一个性能监测区间（Span）的唯一句柄标识
*/
MS_SERVICE_PROFILER_API SpanHandle StartSpan();

/**
    * @brief 记录一个性能监测区间（Span）的开始节点
    * @param name [in] 该性能监测区间（Span）过程名
    * @return 一个性能监测区间（Span）的唯一句柄标识
*/
MS_SERVICE_PROFILER_API SpanHandle StartSpanWithName(const char *name);

/**
    * @brief 为指定性能监测区间（Span）添加标记属性
    * @param msg [in] 标记属性内容
    * @param spanHandle [in] 目标span区间的唯一句柄标识
*/
MS_SERVICE_PROFILER_API void MarkSpanAttr(const char *msg, SpanHandle spanHandle);

/**
    * @brief 性能监测区间（Span）结束
    * @param spanHandle [in] span区间的唯一句柄标识
*/
MS_SERVICE_PROFILER_API void EndSpan(SpanHandle);

/**
    * @brief 记录一个独立事件
    * @param msg [in] 事件描述内容
*/
MS_SERVICE_PROFILER_API void MarkEvent(const char *msg);

/**
    * @brief 启动profiling数据采集
*/
MS_SERVICE_PROFILER_API void StartServerProfiler();

/**
    * @brief 关闭profiling数据采集
*/
MS_SERVICE_PROFILER_API void StopServerProfiler();

/**
    * @brief 检查指定级别的profiling功能是否启用
    * @param level [in] profiling数据采集级别
    * @return true : 该级别profiling功能已开启，false: 未开启
*/
MS_SERVICE_PROFILER_API bool IsEnable(uint32_t level);

/**
    * @brief 检查指定域名数据是否允许落盘
    * @param domainName [in] 待检查域名
    * @return true : 该域名有效/允许相关数据落盘，false: 该域名无效/不允许相关数据落盘
*/
MS_SERVICE_PROFILER_API bool IsValidDomain(const char *domainName);

/**
    * @brief 查询是否启用了域名过滤功能
    * @return true : 域名过滤已启用（仅允许指定域名），false: 域名过滤未启用（允许所有域名）
*/
MS_SERVICE_PROFILER_API bool GetEnableDomainFilter();                  // 20260630 日落

/**
    * @brief 获取当前允许落盘的域名集合
    * @return 当前允许落盘的域名集合，若集合为空表示当前未启用域名过滤功能
*/
MS_SERVICE_PROFILER_API const std::set<std::string> &GetValidDomain(); // 20260630 日落

/**
    * @brief 添加全局元数据信息（键值对形式）
    * @param key [in] 元数据键
    * @param value [in] 元数据值
*/
MS_SERVICE_PROFILER_API void AddMetaInfo(const char *key, const char *value);
}

namespace msServiceProfilerCompatible {
class ServiceProfilerInterface {
public:
    ServiceProfilerInterface(const ServiceProfilerInterface &) = delete;

    ServiceProfilerInterface &operator=(const ServiceProfilerInterface &) = delete;

    ServiceProfilerInterface(ServiceProfilerInterface &&) = delete;

    ServiceProfilerInterface &operator=(ServiceProfilerInterface &&) = delete;

public:
    MS_SERVICE_PROFILER_HIDDEN static ServiceProfilerInterface &GetInstance()
    {
        static ServiceProfilerInterface logManager;
        return logManager;
    }

    ~ServiceProfilerInterface() = default;

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG SpanHandle CallStartSpanWithName(const char *name) const
    {
        return ptrStartSpanWithName_ ? ptrStartSpanWithName_(name) : 0;
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG void CallMarkSpanAttr(const char *msg, SpanHandle spanHandle) const
    {
        if (ptrMarkSpanAttr_) {
            ptrMarkSpanAttr_(msg, spanHandle);
        }
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG void CallEndSpan(SpanHandle spanHandle) const
    {
        if (ptrEndSpan_) {
            ptrEndSpan_(spanHandle);
        }
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG void CallMarkEvent(const char *msg) const
    {
        if (ptrMarkEvent_) {
            ptrMarkEvent_(msg);
        }
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG bool CallIsEnable(uint32_t level) const
    {
        return ptrIsEnable_ && ptrIsEnable_(level);
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG bool CallIsDomainEnable(const char *currentDomain) const
    {
        if (ptrIsValidDomain_) {
            return ptrIsValidDomain_(currentDomain);
        }

        bool domainAllow = true;

        if (!ptrEnableDomainFilter_ || !ptrValidDomain_) {
            return domainAllow;
        }

        if (ptrEnableDomainFilter_()) {
            domainAllow = ptrValidDomain_().find(std::string(currentDomain)) != ptrValidDomain_().end();
        }

        return domainAllow;
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG void CallStartServerProfiler() const
    {
        if (ptrStartServerProfiler_) {
            ptrStartServerProfiler_();
        }
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG void CallStopServerProfiler() const
    {
        if (ptrStopServerProfiler_) {
            ptrStopServerProfiler_();
        }
    }

    MS_SERVICE_PROFILER_HIDDEN MS_SERVICE_INLINE_FLAG void CallAddMetaInfo(const char *key, const char *value) const
    {
        if (ptrAddMetaInfo_) {
            ptrAddMetaInfo_(key, value);
        }
    }

private:
    ServiceProfilerInterface()
    {
        OpenLib();
    };

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    MS_SERVICE_PROFILER_HIDDEN void OpenLibOfTest()
    {
        ptrIsEnable_ = IsEnable;
        ptrStartSpanWithName_ = StartSpanWithName;
        ptrMarkSpanAttr_ = MarkSpanAttr;
        ptrEndSpan_ = EndSpan;
        ptrMarkEvent_ = MarkEvent;
        ptrStartServerProfiler_ = StartServerProfiler;
        ptrStopServerProfiler_ = StopServerProfiler;
        ptrEnableDomainFilter_ = GetEnableDomainFilter;
        ptrValidDomain_ = GetValidDomain;
        ptrIsValidDomain_ = IsValidDomain;
        ptrAddMetaInfo_ = AddMetaInfo;
    }
#endif

    MS_SERVICE_PROFILER_HIDDEN void OpenLib()
    {
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
        OpenLibOfTest();
#else
        char *ascendHomePathPtr = getenv("ASCEND_HOME_PATH");
        if (ascendHomePathPtr == nullptr) {
            printf("Get ASCEND_HOME_PATH failed. Please check that the CANN package is installed.\n"
                   "Run 'source set_env.sh' in the CANN installation path.\n");
            return;
        }
        std::string ascendHomePath(ascendHomePathPtr);
        if (ascendHomePath.empty()) {
            printf("ASCEND_HOME_PATH is empty.\n");
            return;
        }
        char ascendHomeRealPath[PATH_MAX + 1] = {0};
        if (realpath(ascendHomePath.c_str(), ascendHomeRealPath) == nullptr) {
            printf("Failed to canonicalize path: %s", strerror(errno));
            return;
        }
        std::string soName = std::string(ascendHomeRealPath) + "/lib64/libms_service_profiler.so";
        struct stat fileStat;
        if ((stat(soName.c_str(), &fileStat) != 0) || (fileStat.st_mode & S_IRUSR) == 0) {
            printf("File not readable: %s", soName.c_str());
            return;
        }
        auto handle = dlopen(soName.c_str(), RTLD_LAZY);
        if (handle) {
            ptrIsEnable_ = (decltype(IsEnable) *)dlsym(handle, "IsEnable");
            ptrStartSpanWithName_ = (decltype(StartSpanWithName) *)dlsym(handle, "StartSpanWithName");
            ptrMarkSpanAttr_ = (decltype(MarkSpanAttr) *)dlsym(handle, "MarkSpanAttr");
            ptrEndSpan_ = (decltype(EndSpan) *)dlsym(handle, "EndSpan");
            ptrMarkEvent_ = (decltype(MarkEvent) *)dlsym(handle, "MarkEvent");
            ptrStartServerProfiler_ = (decltype(StartServerProfiler) *)dlsym(handle, "StartServerProfiler");
            ptrStopServerProfiler_ = (decltype(StopServerProfiler) *)dlsym(handle, "StopServerProfiler");
            ptrEnableDomainFilter_ = (decltype(GetEnableDomainFilter) *)dlsym(handle, "GetEnableDomainFilter");
            ptrValidDomain_ = (decltype(GetValidDomain) *)dlsym(handle, "GetValidDomain");
            ptrIsValidDomain_ = (decltype(IsValidDomain) *)dlsym(handle, "IsValidDomain");
            ptrAddMetaInfo_ = (decltype(AddMetaInfo) *)dlsym(handle, "AddMetaInfo");
        }
#endif
    }

private:
    decltype(IsEnable) *ptrIsEnable_ = nullptr;
    decltype(StartSpanWithName) *ptrStartSpanWithName_ = nullptr;
    decltype(MarkSpanAttr) *ptrMarkSpanAttr_ = nullptr;
    decltype(EndSpan) *ptrEndSpan_ = nullptr;
    decltype(MarkEvent) *ptrMarkEvent_ = nullptr;
    decltype(StartServerProfiler) *ptrStartServerProfiler_ = nullptr;
    decltype(StopServerProfiler) *ptrStopServerProfiler_ = nullptr;
    decltype(GetEnableDomainFilter) *ptrEnableDomainFilter_ = nullptr;
    decltype(GetValidDomain) *ptrValidDomain_ = nullptr;
    decltype(IsValidDomain) *ptrIsValidDomain_ = nullptr;
    decltype(AddMetaInfo) *ptrAddMetaInfo_ = nullptr;
};
}  // namespace msServiceProfilerCompatible

namespace msServiceProfiler {
enum Level : uint32_t {
    ERROR = 10,                 // 20260630 日落
    INFO = 20,                  // 20260630 日落
    DETAILED = 30,              // 20260630 日落
    VERBOSE = 40,               // 20260630 日落
    LEVEL_CORE_TRACE = 10,      // 最核心的数据，请求关键事件，比如请求到达，请求返回，batch 大小，forward 时长
    LEVEL_OUTLIER_ENENT = 10,   // 异常、关键事件。比如发生了Swap，或者发生了重计算
    LEVEL_NORMAL_TRACE = 20,    // 普通 Trace 数据
    LEVEL_DETAILED_TRACE = 30,  // 包含更多，更大量的详细信息
    L0 = 10,
    L1 = 20,
    L2 = 30
};
}  // namespace msServiceProfiler

#endif
