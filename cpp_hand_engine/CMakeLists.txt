cmake_minimum_required(VERSION 3.16)
project(roops_hand_engine CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Header-only anatomical hand kinematics engine
add_library(roops_hand_engine INTERFACE)
target_include_directories(roops_hand_engine INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)

# Headless CLI demo — no GUI dependency, always built
add_executable(hand_cli_demo src/cli_demo.cpp)
target_link_libraries(hand_cli_demo PRIVATE roops_hand_engine)

option(BUILD_QT_VIEWER "Build the Qt6 3D hand viewer (roops_hand_viewer)" ON)
if(BUILD_QT_VIEWER)
    find_package(Qt6 COMPONENTS Widgets OpenGLWidgets Gui QUIET)
    if(Qt6_FOUND)
        add_subdirectory(qt_viewer)
    else()
        message(WARNING
            "Qt6 (Widgets/OpenGLWidgets/Gui) not found - skipping roops_hand_viewer target.\n"
            "Install with: sudo apt install qt6-base-dev libqt6opengl6-dev qt6-base-dev-tools\n"
            "then re-run cmake.")
    endif()
endif()
