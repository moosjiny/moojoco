set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets OpenGLWidgets Gui)

add_executable(roops_hand_viewer
    main.cpp
    MainWindow.cpp
    MainWindow.h
    HandGLWidget.cpp
    HandGLWidget.h
    MeshBuilder.h
)

target_link_libraries(roops_hand_viewer PRIVATE
    roops_hand_engine
    Qt6::Widgets
    Qt6::OpenGLWidgets
    Qt6::Gui
)
