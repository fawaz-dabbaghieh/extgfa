# CMakeLists.txt
cmake_minimum_required(VERSION 3.20)
project(flatmap_mem CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(
  abseil
  GIT_REPOSITORY https://github.com/abseil/abseil-cpp.git
  GIT_TAG        20240722.0
)

FetchContent_MakeAvailable(abseil)

# --- String-key version ---
add_executable(build_flatmap_mem build_flatmap_mem.cpp)
target_link_libraries(build_flatmap_mem PRIVATE absl::flat_hash_map)
target_compile_options(build_flatmap_mem PRIVATE -O3 -march=native)

# --- Fixed-key version ---
add_executable(build_flatmap_fixed_key build_flatmap_fixed_key.cpp)
target_link_libraries(build_flatmap_fixed_key PRIVATE absl::flat_hash_map absl::hash)
target_compile_options(build_flatmap_fixed_key PRIVATE -O3 -march=native)
