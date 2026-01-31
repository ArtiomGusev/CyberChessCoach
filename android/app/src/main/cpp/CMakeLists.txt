cmake_minimum_required(VERSION 3.22.1)

project("chessengine")

# ✅ Consolidated: Only use native_chess_engine.cpp
add_library(
        chessengine
        SHARED
        native_chess_engine.cpp
        SachmatuLenta.cpp
)

find_library(
        log-lib
        log
)

target_link_libraries(
        chessengine
        ${log-lib}
)
