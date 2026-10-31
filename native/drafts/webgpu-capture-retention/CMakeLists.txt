cmake_minimum_required(VERSION 3.22)
project(GlintDawnRuntimeProbe LANGUAGES C CXX)
if(NOT DEFINED GLINT_OBSERVER_SOURCE OR NOT EXISTS "${GLINT_OBSERVER_SOURCE}")
    message(FATAL_ERROR "GLINT_OBSERVER_SOURCE must name the explicitly patched observer copy")
endif()
set(CMAKE_AR "${GLINT_LIBRARIAN}")
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
set(ABSL_MSVC_STATIC_RUNTIME ON CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(DAWN_FETCH_DEPENDENCIES OFF CACHE BOOL "" FORCE)
set(DAWN_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(DAWN_BUILD_SAMPLES OFF CACHE BOOL "" FORCE)
set(DAWN_BUILD_PROTOBUF OFF CACHE BOOL "" FORCE)
set(DAWN_USE_GLFW OFF CACHE BOOL "" FORCE)
set(DAWN_ENABLE_D3D12 ON CACHE BOOL "" FORCE)
foreach(backend D3D11 VULKAN METAL NULL DESKTOP_GL OPENGLES WEBGPU_ON_WEBGPU)
    set(DAWN_ENABLE_${backend} OFF CACHE BOOL "" FORCE)
endforeach()
set(DAWN_USE_AGILITY_SDK OFF CACHE BOOL "" FORCE)
set(DAWN_USE_BUILT_DXC OFF CACHE BOOL "" FORCE)
set(DAWN_ENABLE_SPIRV_VALIDATION OFF CACHE BOOL "" FORCE)
set(TINT_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(TINT_BUILD_SPV_READER OFF CACHE BOOL "" FORCE)
set(TINT_BUILD_SPV_WRITER OFF CACHE BOOL "" FORCE)
set(TINT_BUILD_CMD_TOOLS OFF CACHE BOOL "" FORCE)
set(TINT_BUILD_BENCHMARKS OFF CACHE BOOL "" FORCE)
set(DAWN_ABSEIL_DIR "${CHROMIUM_ROOT}/third_party/abseil-cpp" CACHE PATH "" FORCE)
set(DAWN_SPIRV_HEADERS_DIR "${CHROMIUM_ROOT}/third_party/spirv-headers/src" CACHE PATH "" FORCE)
set(DAWN_JINJA2_DIR "${CHROMIUM_ROOT}/third_party/jinja2" CACHE PATH "" FORCE)
set(DAWN_MARKUPSAFE_DIR "${CHROMIUM_ROOT}/third_party/markupsafe" CACHE PATH "" FORCE)
add_subdirectory("${DAWN_SOURCE}" dawn)

set(glint_native_sources
    d3d12/GlintTextureProjectionD3D12.cpp
    d3d12/GlintTextureReadbackD3D12.cpp
    d3d12/glint/projected_texture.cc
    d3d12/glint/projected_buffer.cc
    d3d12/glint/texture_capture.cc)
foreach(source IN LISTS glint_native_sources)
    target_sources(dawn_native_objects PRIVATE "${DAWN_SOURCE}/src/dawn/native/${source}")
endforeach()
foreach(source canvas_readback_candidate webgpu_readback_layout webgpu_readback_provenance webgpu_readback_snapshot)
    target_sources(dawn_native_objects PRIVATE "${GLINT_SOURCE}/gpu/command_buffer/common/glint/${source}.cc")
endforeach()
target_sources(dawn_native_objects PRIVATE
    "${GLINT_SOURCE}/gpu/command_buffer/common/glint_webgpu_device_policy.cc"
    "${GLINT_OBSERVER_SOURCE}")
target_include_directories(dawn_native_objects BEFORE PRIVATE
    "${GLINT_SOURCE}/gpu/command_buffer/service"
    "${GLINT_SOURCE}" "${CHROMIUM_ROOT}" "${CHROMIUM_ROOT}/third_party/boringssl/src/include")
target_link_libraries(dawn_native PRIVATE
    "${CHROMIUM_ROOT}/out/CamouFlowNative/obj/third_party/boringssl/boringssl.lib"
    "${CHROMIUM_ROOT}/out/CamouFlowNative/obj/third_party/boringssl/boringssl_asm.lib"
    "${CHROMIUM_ROOT}/out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj"
    bcrypt advapi32)
add_executable(glint_dawn_probe native_probe.cc)
target_link_libraries(glint_dawn_probe PRIVATE dawn::dawn_native dawn::dawn_proc dawn::dawncpp_headers)

target_include_directories(glint_dawn_probe BEFORE PRIVATE "${GLINT_SOURCE}" "${CHROMIUM_ROOT}")

add_executable(glint_wire_probe wire_probe.cc "${DAWN_SOURCE}/src/dawn/utils/TerribleCommandBuffer.cpp" "${GLINT_SOURCE}/gpu/command_buffer/service/glint_webgpu_wire_filter.cc")
target_link_libraries(glint_wire_probe PRIVATE dawn::dawn_native dawn::dawn_proc dawn::dawn_wire dawn::dawncpp_headers)
target_include_directories(glint_wire_probe BEFORE PRIVATE "${GLINT_SOURCE}" "${CHROMIUM_ROOT}" "${DAWN_SOURCE}")
