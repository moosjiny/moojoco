#include "MainWindow.h"
#include "HandGLWidget.h"
#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QDockWidget>
#include <algorithm>

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
    setWindowTitle("ROOPS Humanoid Hand Viewer v2 — Anatomical Finger Joints (Moojoco / hb5u)");
    resize(1280, 800);

    m_handA = std::make_unique<roops::HumanoidHandObject>("Hand A", false);
    m_handB = std::make_unique<roops::HumanoidHandObject>("Hand B", true);

    m_glWidget = new HandGLWidget(this);
    m_glWidget->setHands(m_handA.get(), m_handB.get());
    setCentralWidget(m_glWidget);

    auto* dock = new QDockWidget("Controls", this);
    auto* panel = new QWidget(dock);
    auto* layout = new QVBoxLayout(panel);

    auto* trajGroup = new QGroupBox("Handshake Trajectory (Slider 0.00 - 0.25m)", panel);
    auto* trajLayout = new QVBoxLayout(trajGroup);
    m_trajectorySlider = new QSlider(Qt::Horizontal, trajGroup);
    m_trajectorySlider->setRange(0, 100);
    trajLayout->addWidget(m_trajectorySlider);
    layout->addWidget(trajGroup);

    auto* thumbGroup = new QGroupBox("Thumb Opposition (Hand A + B)", panel);
    auto* thumbLayout = new QVBoxLayout(thumbGroup);
    m_thumbOppositionSlider = new QSlider(Qt::Horizontal, thumbGroup);
    m_thumbOppositionSlider->setRange(0, 100);
    thumbLayout->addWidget(m_thumbOppositionSlider);
    layout->addWidget(thumbGroup);

    auto* fingerGroup = new QGroupBox("Manual Per-Finger Curl Override (Hand A only)", panel);
    auto* fingerLayout = new QVBoxLayout(fingerGroup);
    const char* labels[5] = {"Thumb", "Index", "Middle", "Ring", "Pinky"};
    for (int i = 0; i < 5; ++i) {
        auto* row = new QHBoxLayout();
        row->addWidget(new QLabel(labels[i], fingerGroup));
        m_fingerSliders[i] = new QSlider(Qt::Horizontal, fingerGroup);
        m_fingerSliders[i]->setRange(0, 100);
        row->addWidget(m_fingerSliders[i]);
        fingerLayout->addLayout(row);
        connect(m_fingerSliders[i], &QSlider::valueChanged, this, &MainWindow::onFingerSliderChanged);
    }
    layout->addWidget(fingerGroup);

    m_statusLabel = new QLabel(panel);
    m_statusLabel->setWordWrap(true);
    layout->addWidget(m_statusLabel);
    layout->addStretch();

    dock->setWidget(panel);
    addDockWidget(Qt::RightDockWidgetArea, dock);

    connect(m_trajectorySlider, &QSlider::valueChanged, this, &MainWindow::onTrajectorySliderChanged);
    connect(m_thumbOppositionSlider, &QSlider::valueChanged, this, &MainWindow::onThumbOppositionChanged);

    onTrajectorySliderChanged(0);
}

void MainWindow::onTrajectorySliderChanged(int value) {
    m_manualOverride = false;
    for (auto* s : m_fingerSliders) { s->blockSignals(true); s->setValue(0); s->blockSignals(false); }

    double sliderVal = (value / 100.0) * 0.25;
    double approachRatio = std::min(sliderVal / 0.185, 1.0);
    double claspRatio = std::max((sliderVal - 0.185) / 0.115, 0.0);

    double baseZ = (1.0 - approachRatio) * 3.5 + 1.35;
    double baseCurl = approachRatio * 0.35 + claspRatio * 0.90;

    m_handA->setPosition(-0.25, 3.0, -baseZ);
    m_handB->setPosition(0.25, 3.0, baseZ);
    m_handA->setGraspCurl(baseCurl);
    m_handB->setGraspCurl(baseCurl);

    recompute();
}

void MainWindow::onThumbOppositionChanged(int value) {
    double t = value / 100.0;
    m_handA->setThumbOpposition(t);
    m_handB->setThumbOpposition(t);
    recompute();
}

void MainWindow::onFingerSliderChanged() {
    m_manualOverride = true;
    for (int i = 0; i < 5; ++i) {
        m_handA->fingers[i].setGraspCurl(m_fingerSliders[i]->value() / 100.0);
    }
    recompute();
}

void MainWindow::recompute() {
    m_handA->computeForwardKinematics();
    m_handB->computeForwardKinematics();
    m_glWidget->refreshFromEngine();

    QString mode = m_manualOverride ? "manual per-finger override" : "trajectory-driven";
    m_statusLabel->setText(QString("Mode: %1 | MCP/PIP/DIP anatomical chain active, DIP coupled to PIP at %2x")
                                .arg(mode)
                                .arg(m_handA->fingers[1].dipToPipCoupling));
}
