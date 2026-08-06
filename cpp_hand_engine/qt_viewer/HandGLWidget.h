#pragma once
#include <QOpenGLWidget>
#include <QOpenGLFunctions_3_3_Core>
#include <QOpenGLShaderProgram>
#include <QOpenGLBuffer>
#include <QOpenGLVertexArrayObject>
#include <QMatrix4x4>
#include <QMouseEvent>
#include <QWheelEvent>
#include <map>
#include <memory>
#include <string>

#include "roops/HumanHandKinematics.hpp"
#include "MeshBuilder.h"

// One GPU-resident mesh: VAO + VBO (pos+normal) + IBO.
struct GLMesh {
    std::unique_ptr<QOpenGLVertexArrayObject> vao;
    std::unique_ptr<QOpenGLBuffer> vbo;
    std::unique_ptr<QOpenGLBuffer> ibo;
    int indexCount = 0;
};

class HandGLWidget : public QOpenGLWidget, protected QOpenGLFunctions_3_3_Core {
    Q_OBJECT
public:
    explicit HandGLWidget(QWidget* parent = nullptr);
    ~HandGLWidget() override;

    // The widget only reads FK results (world transforms); it never mutates the engine.
    void setHands(roops::HumanoidHandObject* a, roops::HumanoidHandObject* b);
    void refreshFromEngine(); // call after setGraspCurl()/computeForwardKinematics()

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

    void mousePressEvent(QMouseEvent* e) override;
    void mouseMoveEvent(QMouseEvent* e) override;
    void mouseReleaseEvent(QMouseEvent* e) override;
    void wheelEvent(QWheelEvent* e) override;

private:
    std::unique_ptr<GLMesh> uploadMesh(const MeshData& data);
    void drawMesh(const GLMesh& mesh, const QMatrix4x4& model, const QVector3D& color);
    void drawHand(const roops::HumanoidHandObject* hand, const QVector3D& color);
    void uploadHandMeshes(); // requires a current GL context (initializeGL already ran)
    static QMatrix4x4 toQMatrix(const roops::Mat4& m);

    QOpenGLShaderProgram m_program;
    std::map<std::string, std::unique_ptr<GLMesh>> m_phalanxMeshes; // keyed by segment name
    std::unique_ptr<GLMesh> m_jointSphere;
    std::unique_ptr<GLMesh> m_palmBox;

    roops::HumanoidHandObject* m_handA = nullptr;
    roops::HumanoidHandObject* m_handB = nullptr;

    // orbit camera
    float m_yaw = 25.0f, m_pitch = -18.0f, m_distance = 12.0f;
    QPoint m_lastMousePos;
    bool m_dragging = false;
    bool m_glReady = false; // true once initializeGL() has run and a context exists
};
