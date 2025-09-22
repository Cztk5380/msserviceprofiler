/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef DBDEFINES_H
#define DBDEFINES_H

#include <stdio.h>  // 确保头文件自包含

#define DEBUG_FUNC_START  printf("FUNC:[%s] start\n", __func__)

#endif  // DBDEFINES_H

#ifndef SERVICE_PROFILER_DB_DEFINE_H
#define SERVICE_PROFILER_DB_DEFINE_H

namespace msServiceProfiler {

enum class DBFile {
    SERVICE,
    MSPTI,
    // ADD THE FILE OF DB ON THE LINE ABOVE
    DB_FILE_CNT
};

enum DBStmt : size_t {
    META_INSERT_STMT,
    SERVICE_INSERT_STMT,
    MSPTI_MSTX_INSERT_STMT,
    MSPTI_API_INSERT_STMT,
    MSPTI_KERNEL_INSERT_STMT,
    MSPTI_COMMUNICATION_INSERT_STMT,
    // ADD THE STMT OF DB ON THE LINE ABOVE
    DB_STMT_CNT
};

inline const char *DbFileName(DBFile dbFile)
{
    switch (dbFile) {
        case DBFile::SERVICE:
            return "ms_service";
        case DBFile::MSPTI:
            return "ascend_service_profiler";
        default:
            return "service_prof";
    }
}

}  // namespace msServiceProfiler
#endif
