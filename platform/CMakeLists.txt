
aux_source_directory(${CMAKE_CURRENT_SOURCE_DIR}/securec/src/ SECUREC_SRC)

add_library(securec
        ${SECUREC_SRC}
)
