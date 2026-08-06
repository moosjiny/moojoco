#include "HandGLWidget.h"
#include "MeshBuilder.h"
#include <cmath>

static const char* kVertexShader = R"GLSL(
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProj;
out vec3 vNormal;
out vec3 vWorldPos;
void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    vWorldPos = worldPos.xyz;
    vNormal = mat3(uModel) * aNormal;
    gl_Position = uProj * uView * worldPos;
}
)GLSL";

static const char* kFragmentShader = R"GLSL(
#version 330 core
in vec3 vNormal;
in vec3 vWorldPos;
uniform vec3 uColor;
uniform vec3 uLightDir;
uniform vec3 uEyePos;
out vec4 FragColor;
void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(-uLightDir);
    float diff = max(dot(N, L), 0.0);
    vec3 V = normalize(uEyePos - vWorldPos);
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), 32.0);
    vec3 color = uColor * (0.25 + 0.7 * diff) + vec3(0.3) * spec;
    FragColor = vec4(color, 1.0);
}
)GLSL";

HandGLWidget::HandGLWidget(QWidget* parent) : QOpenGLWidget(parent) {
    QSurfaceFormat fmt;
    fmt.setVersion(3, 3);
    fmt.setProfile(QSurfaceFormat::CoreProfile);
    fmt.setSamples(4);
    setFormat(fmt);
}

HandGLWidget::~HandGLWidget() {
    makeCurrent();
    m_phalanxMeshes.clear();
    m_jointSphere.reset();
    m_palmBox.reset();
    doneCurrent();
}

void HandGLWidget::initializeGL() {
    initializeOpenGLFunctions();
    glClearColor(0.09f, 0.10f, 0.13f, 1.0f);
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_MULTISAMPLE);

    m_program.addShaderFromSourceCode(QOpenGLShader::Vertex, kVertexShader);
    m_program.addShaderFromSourceCode(QOpenGLShader::Fragment, kFragmentShader);
    m_program.link();

    m_jointSphere = uploadMesh(buildSphere(1.0, 8, 12));

    m_glReady = true;
    if (m_handA && m_handB) uploadHandMeshes();
}

std::unique_ptr<GLMesh> HandGLWidget::uploadMesh(const MeshData& data) {
    auto mesh = std::make_unique<GLMesh>();
    mesh->vao = std::make_unique<QOpenGLVertexArrayObject>();
    mesh->vao->create();
    mesh->vao->bind();

    mesh->vbo = std::make_unique<QOpenGLBuffer>(QOpenGLBuffer::VertexBuffer);
    mesh->vbo->create();
    mesh->vbo->bind();
    mesh->vbo->allocate(data.vertices.data(), int(data.vertices.size() * sizeof(float)));

    mesh->ibo = std::make_unique<QOpenGLBuffer>(QOpenGLBuffer::IndexBuffer);
    mesh->ibo->create();
    mesh->ibo->bind();
    mesh->ibo->allocate(data.indices.data(), int(data.indices.size() * sizeof(unsigned int)));

    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(3 * sizeof(float)));

    mesh->vao->release();
    mesh->indexCount = int(data.indices.size());
    return mesh;
}

void HandGLWidget::setHands(roops::HumanoidHandObject* a, roops::HumanoidHandObject* b) {
    m_handA = a;
    m_handB = b;
    // Deferred until initializeGL() has run at least once — the widget has no GL
    // context yet if it hasn't been shown/painted (e.g. called from a dialog ctor).
    if (m_glReady) {
        uploadHandMeshes();
    }
}

void HandGLWidget::uploadHandMeshes() {
    makeCurrent();
    m_phalanxMeshes.clear();
    m_palmBox = uploadMesh(buildBox(m_handA->palm.width, m_handA->palm.height, m_handA->palm.depth));
    for (const auto& f : m_handA->fingers) {
        for (const auto& seg : f.segments) {
            m_phalanxMeshes[seg.name] = uploadMesh(buildTaperedCylinder(seg.length, seg.baseRadius, seg.tipRadius));
        }
    }
    doneCurrent();
    update();
}

void HandGLWidget::refreshFromEngine() { update(); }

QMatrix4x4 HandGLWidget::toQMatrix(const roops::Mat4& m) {
    return QMatrix4x4(
        float(m.m[0]), float(m.m[4]), float(m.m[8]),  float(m.m[12]),
        float(m.m[1]), float(m.m[5]), float(m.m[9]),  float(m.m[13]),
        float(m.m[2]), float(m.m[6]), float(m.m[10]), float(m.m[14]),
        float(m.m[3]), float(m.m[7]), float(m.m[11]), float(m.m[15])
    );
}

void HandGLWidget::drawMesh(const GLMesh& mesh, const QMatrix4x4& model, const QVector3D& color) {
    m_program.setUniformValue("uModel", model);
    m_program.setUniformValue("uColor", color);
    mesh.vao->bind();
    glDrawElements(GL_TRIANGLES, mesh.indexCount, GL_UNSIGNED_INT, nullptr);
    mesh.vao->release();
}

void HandGLWidget::drawHand(const roops::HumanoidHandObject* hand, const QVector3D& color) {
    drawMesh(*m_palmBox, toQMatrix(hand->palm.worldTransform), color * 0.85f);
    for (const auto& f : hand->fingers) {
        for (const auto& seg : f.segments) {
            auto it = m_phalanxMeshes.find(seg.name);
            if (it == m_phalanxMeshes.end()) continue;
            drawMesh(*it->second, toQMatrix(seg.worldOrigin), color);

            QMatrix4x4 jointModel = toQMatrix(seg.worldOrigin);
            jointModel.scale(float(seg.baseRadius));
            drawMesh(*m_jointSphere, jointModel, color * 1.1f);
        }
        // fingertip cap
        const auto& tip = f.segments.back();
        QMatrix4x4 tipModel = toQMatrix(tip.worldTip);
        tipModel.scale(float(tip.tipRadius));
        drawMesh(*m_jointSphere, tipModel, color * 1.1f);
    }
}

void HandGLWidget::resizeGL(int w, int h) { glViewport(0, 0, w, h); }

void HandGLWidget::paintGL() {
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    if (!m_handA || !m_handB) return;

    m_program.bind();

    float yawRad = m_yaw * float(M_PI) / 180.0f;
    float pitchRad = m_pitch * float(M_PI) / 180.0f;
    QVector3D eye(
        m_distance * std::cos(pitchRad) * std::sin(yawRad),
        m_distance * std::sin(pitchRad),
        m_distance * std::cos(pitchRad) * std::cos(yawRad)
    );
    QVector3D target(0.0f, 3.0f, 0.0f);

    QMatrix4x4 view;
    view.lookAt(eye + target, target, QVector3D(0, 1, 0));

    QMatrix4x4 proj;
    float aspect = height() > 0 ? float(width()) / float(height()) : 1.0f;
    proj.perspective(45.0f, aspect, 0.1f, 100.0f);

    m_program.setUniformValue("uView", view);
    m_program.setUniformValue("uProj", proj);
    m_program.setUniformValue("uLightDir", QVector3D(-0.4f, -1.0f, -0.3f));
    m_program.setUniformValue("uEyePos", eye + target);

    drawHand(m_handA, QVector3D(0.22f, 0.75f, 0.95f));   // cyan-ish Hand A
    drawHand(m_handB, QVector3D(0.96f, 0.55f, 0.20f));   // orange-ish Hand B

    m_program.release();
}

void HandGLWidget::mousePressEvent(QMouseEvent* e) {
    m_dragging = true;
    m_lastMousePos = e->pos();
}

void HandGLWidget::mouseMoveEvent(QMouseEvent* e) {
    if (!m_dragging) return;
    QPoint delta = e->pos() - m_lastMousePos;
    m_lastMousePos = e->pos();
    m_yaw += delta.x() * 0.4f;
    m_pitch = std::max(-85.0f, std::min(85.0f, m_pitch - delta.y() * 0.4f));
    update();
}

void HandGLWidget::mouseReleaseEvent(QMouseEvent*) {
    m_dragging = false;
}

void HandGLWidget::wheelEvent(QWheelEvent* e) {
    m_distance = std::max(3.0f, std::min(40.0f, m_distance - e->angleDelta().y() * 0.01f));
    update();
}
