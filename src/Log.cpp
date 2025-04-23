#include <cstdlib>
#include <cstring>
#include "msServiceProfiler/Log.h"

namespace {
    // 静态全局变量存储当前日志级别
    ProfLogLevel g_prof_log_level = PROF_LOG_INFO;
}

void prof_log_init() {
    const char* env_level = getenv("PROF_LOG_LEVEL");
    if (env_level == nullptr) {
        g_prof_log_level = PROF_LOG_INFO; // 默认级别
        return;
    }

    if (strcmp(env_level, "DEBUG") == 0) {
        g_prof_log_level = PROF_LOG_DEBUG;
    } else if (strcmp(env_level, "INFO") == 0) {
        g_prof_log_level = PROF_LOG_INFO;
    } else if (strcmp(env_level, "WARNING") == 0) {
        g_prof_log_level = PROF_LOG_WARNING;
    } else if (strcmp(env_level, "ERROR") == 0) {
        g_prof_log_level = PROF_LOG_ERROR;
    } else if (strcmp(env_level, "NONE") == 0) {
        g_prof_log_level = PROF_LOG_NONE;
    } else {
        g_prof_log_level = PROF_LOG_INFO; // 默认级别
    }
}

ProfLogLevel prof_log_get_level() {
    return g_prof_log_level;
}

void prof_log_set_level(ProfLogLevel level) {
    g_prof_log_level = level;
}

int main() {
    // 初始化日志系统（从环境变量读取级别）
    prof_log_init();

    // 也可以手动设置日志级别
    // prof_log_set_level(PROF_LOG_DEBUG);

    PROF_LOGD("Debug message: %s", "This will show if level is DEBUG");
    PROF_LOGI("Info message: %d", 42);
    PROF_LOGW("Warning message");
    PROF_LOGE("Error message");

    return 0;
}
