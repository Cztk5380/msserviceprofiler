/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2024-12-16
 */

#ifndef MS_SERVICE_PROFILER_MSPTI_H
#define MS_SERVICE_PROFILER_MSPTI_H

#include <cstdint>

#ifdef __cplusplus
extern "C" {
#endif

#define MSTX_INVALID_ID 0

typedef uint64_t  mstxRangeId;

#ifndef MSPTI_SUCCESS
static const int MSPTI_SUCCESS = 0,    // MSPTI执行成功，无错误
static const int MSPTI_ERROR_INVALID_PARAMETER = 1,    // funcBufferRequested或funcBufferCompleted为NULL时返回，表示MSPTI执行失败
static const int MSPTI_ERROR_MULTIPLE_SUBSCRIBERS_NOT_SUPPORTED = 2,    // 已存在MSPTI用户时返回，表示MSPTI执行失败
static const int MSPTI_ERROR_MAX_LIMIT_REACHED = 3,    // Activity Buffer没有更多的Record数据时返回，表示MSPTI执行失败
static const int MSPTI_ERROR_DEVICE_OFFLINE = 4,    // 无法获取DEVICE侧信息
static const int MSPTI_ERROR_INNER = 999,    // 无法初始化MSPTI时返回，表示MSPTI执行失败
static const int MSPTI_ERROR_FOECE_INT = 0x7fffffff;
#endif

void mstxMarkA(const char* message, aclrtStream stream);
mstxRangeId mstxRangeStartA(const char* message, aclrtStream stream);
void mstxRangeEnd(mstxRangeId id);

typedef int msptiResult;
typedef int msptiSubscriberHandle;

typedef enum {
	MSPTI_ACTIVITY_KIND_INVALID = 0,   // 非法值
	MSPTI_ACTIVITY_KIND_MARKER = 1,   // MSPTI打点能力（标记瞬时时刻）的Activity Record类型，支持最大打点个数为uin32_t最大值，调用结构体msptiActivityMarker
	MSPTI_ACTIVITY_KIND_KERNEL = 2,   // aclnn场景下，计算类算子信息采集的Activity Record类型，调用结构体msptiActivityKernel
	MSPTI_ACTIVITY_KIND_API = 3,   // aclnn场景下，aclnn组件信息采集Activity Record类型，调用结构体msptiActivityApi
	MSPTI_ACTIVITY_KIND_HCCL = 4   // 通信算子采集Activity Record类型，调用结构体msptiActivitHccl
} msptiActivityKind;

typedef struct msptiActivity {
	msptiActivityKind kind;   // Activity类型
};

typedef struct msptiActivityApi {
	msptiActivityKind kind;   // Activity Record类型MSPTI_ACTIVITY_KIND_API
	uint64_t start;   // API执行的开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集API的时间戳信息
	uint64_t end;   // API执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集API的时间戳信息
	struct {
		uint32_t processId;   // API运行设备的进程ID
		uint32_t threadId;   // API运行流的线程ID
	} pt;
	uint64_t correlationId;   // API的关联ID。每个API执行都被分配一个唯一的关联ID，该关联ID与启动API的驱动程序或运行时API Activity Record的关联ID相同
	const char* name;   // API的名称，该名称在整个Activity Record中保持一致，不建议修改
};

typedef struct msptiActivitHccl {
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
};

typedef struct msptiActivityKernel {
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
};

msptiResult msptiActivityRegisterCallbacks(void (*func1(uint8_t, size_t, size_t)), void (*func2(uint8_t, size_t, size_t)));
msptiResult msptiActivityEnable(int);
msptiResult msptiActivityGetNextRecord(unit8_t *buffer, size_t validBufferSizeBytes, msptiActivity **record);
msptiResult msptiActivityFlushAll(int);
msptiResult msptiSubscribe(int, int, int);

#ifdef __cplusplus
}
#endif

#endif //_MS_TOOLS_EXT_H

