#pragma once
#include <QMainWindow>
#include <QSlider>
#include <QLabel>
#include <QCheckBox>
#include <QDoubleSpinBox>
#include <QFormLayout>
#include <memory>
#include "roops/HumanHandKinematics.hpp"

class HandGLWidget;

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);

private slots:
    void onTrajectorySliderChanged(int value);
    void onFingerSliderChanged();
    void onThumbOppositionChanged(int value);
    void onManualPoseChanged();
    void onPositionOverrideToggled(bool checked);

private:
    QSlider* addFingerSlider(QWidget* panel, const QString& label);
    QDoubleSpinBox* addPoseSpin(QFormLayout* form, const QString& label, double minV, double maxV, double val,
                                 double sliderScale, QSlider** sliderOut);
    void syncPoseSpinboxes(); // reflect engine's current position/rotation into the sliders/spinboxes without re-triggering signals
    void recompute();

    std::unique_ptr<roops::HumanoidHandObject> m_handA;
    std::unique_ptr<roops::HumanoidHandObject> m_handB;
    HandGLWidget* m_glWidget = nullptr;

    QSlider* m_trajectorySlider = nullptr;
    QSlider* m_thumbOppositionSlider = nullptr;
    QSlider* m_fingerSliders[5] = {nullptr, nullptr, nullptr, nullptr, nullptr}; // manual override, Hand A only
    QLabel* m_statusLabel = nullptr;
    bool m_manualOverride = false;

    // Manual position/rotation override (X,Y,Z position + RX,RY,RZ rotation in degrees),
    // each axis exposed as a linked slider + spinbox pair.
    static constexpr double kPosSliderScale = 20.0; // slider int = value * 20  (0.05 resolution)
    static constexpr double kRotSliderScale = 1.0;  // slider int = value * 1  (1 degree resolution)

    QCheckBox* m_positionOverrideCheck = nullptr;
    QDoubleSpinBox* m_posSpinA[3] = {nullptr, nullptr, nullptr};
    QDoubleSpinBox* m_rotSpinA[3] = {nullptr, nullptr, nullptr};
    QDoubleSpinBox* m_posSpinB[3] = {nullptr, nullptr, nullptr};
    QDoubleSpinBox* m_rotSpinB[3] = {nullptr, nullptr, nullptr};
    QSlider* m_posSliderA[3] = {nullptr, nullptr, nullptr};
    QSlider* m_rotSliderA[3] = {nullptr, nullptr, nullptr};
    QSlider* m_posSliderB[3] = {nullptr, nullptr, nullptr};
    QSlider* m_rotSliderB[3] = {nullptr, nullptr, nullptr};
    bool m_positionOverride = false;
};
