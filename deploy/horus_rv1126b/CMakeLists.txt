cmake_minimum_required(VERSION 3.15)
project(sorting_horus_integration_demo LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(
    sorting_horus_integration_demo
    sorting_horus_integration.cpp
)

target_compile_options(
    sorting_horus_integration_demo
    PRIVATE
    -Wall
    -Wextra
    -pedantic
)
