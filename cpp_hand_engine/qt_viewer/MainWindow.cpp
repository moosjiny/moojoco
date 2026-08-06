#include "MainWindow.h"
#include "HandGLWidget.h"
#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QDockWidget>
#include <algorithm>
#include <cmath>

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

    auto* poseGroup = new QGroupBox("Manual Position / Rotation (overrides trajectory)", panel);
    auto* poseLayout = new QVBoxLayout(poseGroup);
    m_positionOverrideCheck = new QCheckBox("Enable manual pose override", poseGroup);
    poseLayout->addWidget(m_positionOverrideCheck);

    auto* poseRow = new QHBoxLayout();

    auto* handAPoseGroup = new QGroupBox("Hand A", poseGroup);
    auto* handAForm = new QFormLayout(handAPoseGroup);
    m_posSpinA[0] = addPoseSpin(handAForm, "X", -5.0, 5.0, -0.25, kPosSliderScale, &m_posSliderA[0]);
    m_posSpinA[1] = addPoseSpin(handAForm, "Y", -5.0, 10.0, 3.0, kPosSliderScale, &m_posSliderA[1]);
    m_posSpinA[2] = addPoseSpin(handAForm, "Z", -5.0, 10.0, -1.35, kPosSliderScale, &m_posSliderA[2]);
    m_rotSpinA[0] = addPoseSpin(handAForm, "RX (deg)", -180.0, 180.0, 0.0, kRotSliderScale, &m_rotSliderA[0]);
    m_rotSpinA[1] = addPoseSpin(handAForm, "RY (deg)", -180.0, 180.0, 0.0, kRotSliderScale, &m_rotSliderA[1]);
    m_rotSpinA[2] = addPoseSpin(handAForm, "RZ (deg)", -180.0, 180.0, 0.0, kRotSliderScale, &m_rotSliderA[2]);
    poseRow->addWidget(handAPoseGroup);

    auto* handBPoseGroup = new QGroupBox("Hand B", poseGroup);
    auto* handBForm = new QFormLayout(handBPoseGroup);
    m_posSpinB[0] = addPoseSpin(handBForm, "X", -5.0, 5.0, 0.25, kPosSliderScale, &m_posSliderB[0]);
    m_posSpinB[1] = addPoseSpin(handBForm, "Y", -5.0, 10.0, 3.0, kPosSliderScale, &m_posSliderB[1]);
    m_posSpinB[2] = addPoseSpin(handBForm, "Z", -5.0, 10.0, 1.35, kPosSliderScale, &m_posSliderB[2]);
    m_rotSpinB[0] = addPoseSpin(handBForm, "RX (deg)", -180.0, 180.0, 0.0, kRotSliderScale, &m_rotSliderB[0]);
    m_rotSpinB[1] = addPoseSpin(handBForm, "RY (deg)", -180.0, 180.0, 180.0, kRotSliderScale, &m_rotSliderB[1]);
    m_rotSpinB[2] = addPoseSpin(handBForm, "RZ (deg)", -180.0, 180.0, 0.0, kRotSliderScale, &m_rotSliderB[2]);
    poseRow->addWidget(handBPoseGroup);

    poseLayout->addLayout(poseRow);
    layout->addWidget(poseGroup);

    connect(m_positionOverrideCheck, &QCheckBox::toggled, this, &MainWindow::onPositionOverrideToggled);

    m_statusLabel = new QLabel(panel);
    m_statusLabel->setWordWrap(true);
    layout->addWidget(m_statusLabel);

    m_collisionLabel = new QLabel(panel);
    m_collisionLabel->setWordWrap(true);
    layout->addWidget(m_collisionLabel);
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

    if (!m_positionOverride) {
        m_handA->setPosition(-0.25, 3.0, -baseZ);
        m_handB->setPosition(0.25, 3.0, baseZ);
        syncPoseSpinboxes();
    }
    m_handA->setGraspCurl(baseCurl);
    m_handB->setGraspCurl(baseCurl);

    recompute();
}

QDoubleSpinBox* MainWindow::addPoseSpin(QFormLayout* form, const QString& label, double minV, double maxV, double val,
                                         double sliderScale, QSlider** sliderOut) {
    auto* spin = new QDoubleSpinBox();
    spin->setRange(minV, maxV);
    spin->setSingleStep(1.0 / sliderScale);
    spin->setDecimals(2);
    spin->setValue(val);

    auto* slider = new QSlider(Qt::Horizontal);
    slider->setRange(int(std::round(minV * sliderScale)), int(std::round(maxV * sliderScale)));
    slider->setValue(int(std::round(val * sliderScale)));

    auto* row = new QWidget();
    auto* rowLayout = new QHBoxLayout(row);
    rowLayout->setContentsMargins(0, 0, 0, 0);
    rowLayout->addWidget(slider, 1);
    rowLayout->addWidget(spin);
    form->addRow(label, row);

    // Keep slider and spinbox mirroring each other, then forward either change to the engine.
    connect(slider, &QSlider::valueChanged, this, [spin, slider, sliderScale]() {
        spin->blockSignals(true);
        spin->setValue(slider->value() / sliderScale);
        spin->blockSignals(false);
    });
    connect(spin, QOverload<double>::of(&QDoubleSpinBox::valueChanged), this, [slider, sliderScale](double v) {
        slider->blockSignals(true);
        slider->setValue(int(std::round(v * sliderScale)));
        slider->blockSignals(false);
    });
    connect(slider, &QSlider::valueChanged, this, &MainWindow::onManualPoseChanged);
    connect(spin, QOverload<double>::of(&QDoubleSpinBox::valueChanged), this, &MainWindow::onManualPoseChanged);

    if (sliderOut) *sliderOut = slider;
    return spin;
}

void MainWindow::syncPoseSpinboxes() {
    auto sync = [](QDoubleSpinBox* posSpin[3], QSlider* posSlider[3], QDoubleSpinBox* rotSpin[3], QSlider* rotSlider[3],
                    const roops::HumanoidHandObject* hand) {
        const roops::Vec3& p = hand->position;
        const roops::Vec3& r = hand->rotation;
        double posVal[3] = {p.x, p.y, p.z};
        double rotVal[3] = {r.x * 180.0 / M_PI, r.y * 180.0 / M_PI, r.z * 180.0 / M_PI};
        for (int i = 0; i < 3; ++i) {
            posSpin[i]->blockSignals(true);
            posSpin[i]->setValue(posVal[i]);
            posSpin[i]->blockSignals(false);
            posSlider[i]->blockSignals(true);
            posSlider[i]->setValue(int(std::round(posVal[i] * kPosSliderScale)));
            posSlider[i]->blockSignals(false);

            rotSpin[i]->blockSignals(true);
            rotSpin[i]->setValue(rotVal[i]);
            rotSpin[i]->blockSignals(false);
            rotSlider[i]->blockSignals(true);
            rotSlider[i]->setValue(int(std::round(rotVal[i] * kRotSliderScale)));
            rotSlider[i]->blockSignals(false);
        }
    };
    sync(m_posSpinA, m_posSliderA, m_rotSpinA, m_rotSliderA, m_handA.get());
    sync(m_posSpinB, m_posSliderB, m_rotSpinB, m_rotSliderB, m_handB.get());
}

void MainWindow::onManualPoseChanged() {
    if (!m_positionOverride) return;
    m_handA->setPosition(m_posSpinA[0]->value(), m_posSpinA[1]->value(), m_posSpinA[2]->value());
    m_handA->setRotation(m_rotSpinA[0]->value() * M_PI / 180.0, m_rotSpinA[1]->value() * M_PI / 180.0, m_rotSpinA[2]->value() * M_PI / 180.0);
    m_handB->setPosition(m_posSpinB[0]->value(), m_posSpinB[1]->value(), m_posSpinB[2]->value());
    m_handB->setRotation(m_rotSpinB[0]->value() * M_PI / 180.0, m_rotSpinB[1]->value() * M_PI / 180.0, m_rotSpinB[2]->value() * M_PI / 180.0);
    recompute();
}

void MainWindow::onPositionOverrideToggled(bool checked) {
    m_positionOverride = checked;
    if (checked) {
        syncPoseSpinboxes(); // seed spinboxes with the trajectory's current pose so toggling on doesn't jump the hands
    } else {
        onTrajectorySliderChanged(m_trajectorySlider->value()); // hand pose control back to the trajectory
    }
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
    updateCollisionGuard(); // may revert a manual drag that would cause hand-vs-hand overlap
    m_glWidget->refreshFromEngine();

    QString mode = m_manualOverride ? "manual per-finger override" : "trajectory-driven";
    m_statusLabel->setText(QString("Mode: %1 | MCP/PIP/DIP anatomical chain active, DIP coupled to PIP at %2x")
                                .arg(mode)
                                .arg(m_handA->fingers[1].dipToPipCoupling));
}

void MainWindow::updateCollisionGuard() {
    auto result = roops::checkHandCollision(*m_handA, *m_handB);

    if (result.colliding && m_positionOverride) {
        // A manual drag pushed the hands into each other — revert to the last verified
        // non-colliding wrist pose rather than letting the geometry pass through itself.
        m_handA->position = m_lastValidPosA;
        m_handA->rotation = m_lastValidRotA;
        m_handB->position = m_lastValidPosB;
        m_handB->rotation = m_lastValidRotB;
        m_handA->computeForwardKinematics();
        m_handB->computeForwardKinematics();
        syncPoseSpinboxes();

        m_collisionLabel->setStyleSheet("color: #dc2626; font-weight: bold;");
        m_collisionLabel->setText(QString("Collision blocked: %1 vs %2 (overlap %3) — pose reverted")
                                       .arg(QString::fromStdString(result.partA))
                                       .arg(QString::fromStdString(result.partB))
                                       .arg(result.worstPenetration, 0, 'f', 3));
    } else if (result.colliding) {
        // Trajectory/grasp-driven contact (e.g. interlocking fingers during a clasp) is
        // expected during a handshake, so this is reported but not blocked.
        m_collisionLabel->setStyleSheet("color: #d97706; font-weight: bold;");
        m_collisionLabel->setText(QString("Contact: %1 vs %2 (overlap %3)")
                                       .arg(QString::fromStdString(result.partA))
                                       .arg(QString::fromStdString(result.partB))
                                       .arg(result.worstPenetration, 0, 'f', 3));
    } else {
        m_lastValidPosA = m_handA->position; m_lastValidRotA = m_handA->rotation;
        m_lastValidPosB = m_handB->position; m_lastValidRotB = m_handB->rotation;
        m_collisionLabel->setStyleSheet("color: #16a34a;");
        m_collisionLabel->setText("No collision (min gap OK)");
    }
}
