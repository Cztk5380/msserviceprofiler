/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2024-12-16
 */

#ifndef MS_SERVICE_PROFILER_ACL_H
#define MS_SERVICE_PROFILER_ACL_H

#include <cstdint>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef ACL_PROF_ACL_API
#define ACL_PROF_ACL_API                0x0001ULL
#define ACL_PROF_TASK_TIME              0x0002ULL
#define ACL_PROF_AICORE_METRICS         0x0004ULL
#define ACL_PROF_AICPU                  0x0008ULL
#define ACL_PROF_L2CACHE                0x0010ULL
#define ACL_PROF_HCCL_TRACE             0x0020ULL
#define ACL_PROF_TRAINING_TRACE         0x0040ULL
#define ACL_PROF_MSPROFTX               0x0080ULL
#define ACL_PROF_RUNTIME_API            0x0100ULL
#define ACL_PROF_TASK_TIME_L0           0x0800ULL
#define ACL_PROF_TASK_MEMORY            0x1000ULL
#define ACL_PROF_OP_ATTR                0x4000ULL
#endif

#ifndef INC_EXTERNAL_ACL_PROF_H_
static const int ACL_ERROR_NONE = 0;
static const int ACL_SUCCESS = 0;
static const int ACL_ERROR_REPEAT_INITIALIZE = 100002;
#endif

typedef void *aclrtStream;
typedef void *aclrtContext;
typedef int aclError;
aclError aclInit(const char *configPath);
aclError aclrtSetDevice(int32_t deviceId);
aclError aclrtCreateContext(aclrtContext *context, int32_t deviceId);
aclError aclrtCreateStream(aclrtStream *stream);
aclError aclrtGetDevice(int32_t *deviceId);
#ifdef __cplusplus
}
#endif
#endif //_ACL_H
