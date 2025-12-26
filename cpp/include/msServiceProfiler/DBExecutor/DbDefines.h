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

#ifndef SERVICE_PROFILER_DB_DEFINE_H
#define SERVICE_PROFILER_DB_DEFINE_H

#include <cstddef>

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
