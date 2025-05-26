/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2025-5-15
 */

#ifndef MS_SERVICE_PROFILER_MSPTI_H
#define MS_SERVICE_PROFILER_MSPTI_H

#include <cstdint>
#include <iostream>

#ifdef __cplusplus
extern "C" {
#endif

#define ACTIVITY_STRUCT_ALIGNMENT 8
#if defined(_WIN32)
#define START_PACKED_ALIGNMENT __pragma(pack(push, 1))
#define PACKED_ALIGNMENT __declspec(align(ACTIVITY_STRUCT_ALIGNMENT))
#define END_PACKED_ALIGNMENT __pragma(pack(pop))
#elif defined(__GNUC__)
#define START_PACKED_ALIGNMENT
#define PACKED_ALIGNMENT __attribute__((__packed__)) __attribute__((aligned(ACTIVITY_STRUCT_ALIGNMENT)))
#define END_PACKED_ALIGNMENT
#else
#define START_PACKED_ALIGNMENT
#define PACKED_ALIGNMENT
#define END_PACKED_ALIGNMENT
#endif

typedef struct msptiSubscriber_st *msptiSubscriberHandle;

typedef enum {
    /**
    * The activity record is invalid.
    */
    MSPTI_ACTIVITY_KIND_INVALID                         = 0,
    MSPTI_ACTIVITY_KIND_MARKER                          = 1,
    MSPTI_ACTIVITY_KIND_KERNEL                          = 2,
    MSPTI_ACTIVITY_KIND_API                             = 3,
    MSPTI_ACTIVITY_KIND_HCCL                            = 4,
    MSPTI_ACTIVITY_KIND_MEMORY                          = 5,
    MSPTI_ACTIVITY_KIND_MEMSET                          = 6,
    MSPTI_ACTIVITY_KIND_MEMCPY                          = 7,
    MSPTI_ACTIVITY_KIND_EXTERNAL_CORRELATION            = 8,
    MSPTI_ACTIVITY_KIND_COMMUNICATION                   = 9,
    MSPTI_ACTIVITY_KIND_COUNT,
    MSPTI_ACTIVITY_KIND_FORCE_INT                       = 0x7fffffff
} msptiActivityKind;

typedef enum {
    MSPTI_SUCCESS                                       = 0,
    MSPTI_ERROR_INVALID_PARAMETER                       = 1,
    MSPTI_ERROR_MULTIPLE_SUBSCRIBERS_NOT_SUPPORTED      = 2,
    MSPTI_ERROR_MAX_LIMIT_REACHED                       = 3,
    MSPTI_ERROR_DEVICE_OFFLINE                          = 4,
    MSPTI_ERROR_QUEUE_EMPTY                             = 5,
    MSPTI_ERROR_INNER                                   = 999,
    MSPTI_ERROR_FOECE_INT                               = 0x7fffffff
} msptiResult;

typedef enum {
    MSPTI_ACTIVITY_FLAG_NONE = 0,
    MSPTI_ACTIVITY_FLAG_MARKER_INSTANTANEOUS = 1 << 0,
    MSPTI_ACTIVITY_FLAG_MARKER_START = 1 << 1,
    MSPTI_ACTIVITY_FLAG_MARKER_END = 1 << 2,
    MSPTI_ACTIVITY_FLAG_MARKER_INSTANTANEOUS_WITH_DEVICE = 1 << 3,
    MSPTI_ACTIVITY_FLAG_MARKER_START_WITH_DEVICE = 1 << 4,
    MSPTI_ACTIVITY_FLAG_MARKER_END_WITH_DEVICE = 1 << 5
} msptiActivityFlag;

typedef enum {
    MSPTI_ACTIVITY_SOURCE_KIND_HOST = 0,
    MSPTI_ACTIVITY_SOURCE_KIND_DEVICE = 1
} msptiActivitySourceKind;

typedef union PACKED_ALIGNMENT {
    struct {
        uint32_t processId;
        uint32_t threadId;
    } pt;
    struct {
        uint32_t deviceId;
        uint32_t streamId;
    } ds;
} msptiObjectId;

typedef struct PACKED_ALIGNMENT {
    msptiActivityKind kind;
} msptiActivity;

typedef struct PACKED_ALIGNMENT {
    msptiActivityKind kind;   // Activity Record类型MSPTI_ACTIVITY_KIND_API
    uint64_t start;   // API执行的开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集API的时间戳信息
    uint64_t end;   // API执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集API的时间戳信息
    struct {
        uint32_t processId;   // API运行设备的进程ID
        uint32_t threadId;   // API运行流的线程ID
    } pt;
    uint64_t correlationId;   // API的关联ID。每个API执行都被分配一个唯一的关联ID，该关联ID与启动API的驱动程序或运行时API Activity Record的关联ID相同
    const char* name;   // API的名称，该名称在整个Activity Record中保持一致，不建议修改
} msptiActivityApi;

typedef struct PACKED_ALIGNMENT {
    msptiActivityKind kind;   // Activity Record类型MSPTI_ACTIVITY_KIND_HCCL
    uint64_t start;   // 通信算子在NPU设备上执行开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集通信算子的时间戳信息
    uint64_t end;   // 通信算子执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集通信算子的时间戳信息
    struct {
        uint32_t deviceId;   // 通信算子运行设备的Device ID
        uint32_t streamId;   // 通信算子运行流的Stream ID
    } ds;
    uint64_t bandWidth;   // 通信算子运行时的带宽，单位GB/s
    const char *name;   // 通信算子的名称
    const char *commName;   // 通信域的名称
} msptiActivityHccl;

typedef struct PACKED_ALIGNMENT {
    msptiActivityKind kind;   // Activity Record类型MSPTI_ACTIVITY_KIND_KERNEL
    uint64_t start;   // Kernel在NPU设备上执行开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集kernel的时间戳信息
    uint64_t end;   // kernel执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集kernel的时间戳信息
    struct {
        uint32_t deviceId;   // kernel运行设备的Device ID
        uint32_t streamId;   // kernel运行流的Stream ID
    } ds;
    uint64_t correlationId;   // Runtime在Launch Kernel时生成的唯一ID，其它Activity可通过该值与Kernel进行关联
    const char *type;   // kernel的类型
    const char *name;   // kernel的名称，该名称在整个Activity Record中保持一致，不建议修改
} msptiActivityKernel;

typedef struct PACKED_ALIGNMENT {
    msptiActivityKind kind;
    msptiActivityFlag flag;
    msptiActivitySourceKind sourceKind;
    uint64_t timestamp;
    uint64_t id;
    msptiObjectId objectId;
    const char *name;
    const char *domain;
} msptiActivityMarker;

typedef enum {
    MSPTI_ACTIVITY_COMMUNICATION_INT8 = 0,
    MSPTI_ACTIVITY_COMMUNICATION_INT16 = 1,
    MSPTI_ACTIVITY_COMMUNICATION_INT32 = 2,
    MSPTI_ACTIVITY_COMMUNICATION_FP16 = 3,
    MSPTI_ACTIVITY_COMMUNICATION_FP32 = 4,
    MSPTI_ACTIVITY_COMMUNICATION_INT64 = 5,
    MSPTI_ACTIVITY_COMMUNICATION_UINT64 = 6,
    MSPTI_ACTIVITY_COMMUNICATION_UINT8 = 7,
    MSPTI_ACTIVITY_COMMUNICATION_UINT16 = 8,
    MSPTI_ACTIVITY_COMMUNICATION_UINT32 = 9,
    MSPTI_ACTIVITY_COMMUNICATION_FP64 = 10,
    MSPTI_ACTIVITY_COMMUNICATION_BFP16 = 11,
    MSPTI_ACTIVITY_COMMUNICATION_INT128 = 12,
    MSPTI_ACTIVITY_COMMUNICATION_INVALID_TYPE = 0x0000FFFF
} msptiCommunicationDataType;

typedef struct PACKED_ALIGNMENT {
    msptiActivityKind kind;   // Activity Record类型MSPTI_ACTIVITY_KIND_COMMUNICATION
    msptiCommunicationDataType dataType;   // 通信算子数据类型
    uint64_t count;   // 通信数据量
    struct {
        uint32_t deviceId;   // 通信算子运行设备的Device ID
        uint32_t streamId;   // 通信算子运行流的Stream ID
    } ds;
    uint64_t start;   // 通信算子在NPU设备上执行开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集通信算子的时间戳信息
    uint64_t end;   // 通信算子执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集通信算子的时间戳信息
    const char* algType;   // 通信算子采用的通信算法
    const char* name;   // 通信算子的名称
    const char* commName;   // 通信算子所在通信域的名称
    uint64_t correlationId;
} msptiActivityCommunication;

typedef void (*bufferRequestFunctionPtr)(uint8_t**, size_t*, size_t*);
typedef void (*bufferCompleteFunctionPtr)(uint8_t*, size_t, size_t);

msptiResult msptiActivityRegisterCallbacks(bufferRequestFunctionPtr, bufferCompleteFunctionPtr);
msptiResult msptiActivityEnable(int);
msptiResult msptiActivityGetNextRecord(uint8_t*, size_t, msptiActivity**);
msptiResult msptiActivityFlushAll(int);
msptiResult msptiSubscribe(msptiSubscriberHandle*, int*, int*);
msptiResult msptiUnsubscribe(msptiSubscriberHandle);

#ifdef __cplusplus
}
#endif

#endif //_MS_TOOLS_EXT_H

