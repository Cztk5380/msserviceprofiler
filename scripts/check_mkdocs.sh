#!/bin/bash
#
# readthedocs资料构建 检查 mkdocs.yml 与 docs 目录一致性：
# 1. mkdocs.yml 中配置的文件不存在 -> 报错退出 1
# 2. docs 目录下的 .md 文件未配置到 mkdocs.yml 且不在排除表EXCLUDED_MD中 -> 报错退出 1
#
# 用法: ./scripts/check-mkdocs.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

MKDOCS="${1:-mkdocs.yml}"
DOCS_DIR="docs"

# 确认不应添加到 mkdocs.yml 的 .md 文件（相对 docs 的路径）
# 确认下述文件将不在readthedocs显示
EXCLUDED_MD=(
  zh/cpp_api/trace_data_monitoring/Span_1.md
  zh/overview.md
)

if [[ ! -f "$MKDOCS" ]]; then
  echo "错误: 未找到 $MKDOCS"
  exit 1
fi

# 判断路径是否在排除表中
is_excluded() {
  local f="$1"
  for e in "${EXCLUDED_MD[@]}"; do
    [[ "$e" == "$f" ]] && return 0
  done
  return 1
}

# 从 mkdocs.yml 抽取所有 .md 路径（相对 docs）
get_nav_paths() {
  sed -n '/^nav:/,/^[a-z_]/p' "$MKDOCS" | \
    grep '\.md' | \
    sed -E 's/^[^:]*:[[:space:]]+(.+\.md)[[:space:]]*$/\1/' | \
    sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
    grep -E '\.md$' | \
    sort -u
}

# 获取 docs 目录下所有 .md 文件（相对 docs 的路径）
get_all_docs_md() {
  if [[ ! -d "$DOCS_DIR" ]]; then
    return
  fi
  (cd "$DOCS_DIR" && find . -type f -name "*.md") | sed 's|^\./||' | sort -u
}

NAV_PATHS=$(get_nav_paths)
ERRORS=""

# 1. 检查 mkdocs.yml 中配置的文档是否存在
while IFS= read -r p; do
  [[ -z "$p" ]] && continue
  if [[ ! -f "$DOCS_DIR/$p" ]]; then
    ERRORS="${ERRORS}  - $p\n"
  fi
done <<< "$NAV_PATHS"

if [[ -n "$ERRORS" ]]; then
  echo "错误: 以下文档链接已失效:"
  echo -e "$ERRORS"
  exit 1
fi

# 2. 检查 docs 下 .md 文件是否已配置到 mkdocs.yml 或在排除表中
UNCGF=""
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if echo "$NAV_PATHS" | grep -qxF "$f"; then
    continue
  fi
  if is_excluded "$f"; then
    continue
  fi
  UNCGF="${UNCGF}  - $f\n"
done <<< "$(get_all_docs_md)"

if [[ -n "$UNCGF" ]]; then
  echo "错误: docs 目录下以下 .md 文件尚未配置到 mkdocs.yml:"
  echo -e "$UNCGF"
  echo "请将上述文件添加到 mkdocs.yml 配置，或加入本脚本的 EXCLUDED_MD 排除表。"
  exit 1
fi

exit 0
