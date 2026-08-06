#pragma once
#include <QMainWindow>
#include <QSlider>
#include <QLabel>
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

private:
    QSlider* addFingerSlider(QWidget* panel, const QString& label);
    void recompute();

    std::unique_ptr<roops::HumanoidHandObject> m_handA;
    std::unique_ptr<roops::HumanoidHandObject> m_handB;
    HandGLWidget* m_glWidget = nullptr;

    QSlider* m_trajectorySlider = nullptr;
    QSlider* m_thumbOppositionSlider = nullptr;
    QSlider* m_fingerSliders[5] = {nullptr, nullptr, nullptr, nullptr, nullptr}; // manual override, Hand A only
    QLabel* m_statusLabel = nullptr;
    bool m_manualOverride = false;
};
