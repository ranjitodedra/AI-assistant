#!/usr/bin/env python3
"""
Copilot-style animated icon using PySide6.
Features:
 - slow head bob (translate + slight rotate)
 - occasional blink
 - mouth bounce
"""
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, QTimer, Qt
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
import sys
import random

class CopilotIcon(QWidget):
    def __init__(self, parent=None, size=160):
        super().__init__(parent)
        self.setFixedSize(size, size)
        # animation-controlled properties
        self._bob = 0.0         # vertical bob offset (px)
        self._rotation = 0.0    # small rotation (degrees)
        self._eye_scale = 1.0   # 1.0 open, 0.12 closed
        self._mouth_scale = 1.0
        # Setup animations
        self.setup_animations()

    # Property: bob
    def getBob(self):
        return self._bob
    def setBob(self, v):
        self._bob = v
        self.update()
    bob = Property(float, getBob, setBob)

    # Property: rotation
    def getRotation(self):
        return self._rotation
    def setRotation(self, v):
        self._rotation = v
        self.update()
    rotation = Property(float, getRotation, setRotation)

    # Property: eye_scale
    def getEyeScale(self):
        return self._eye_scale
    def setEyeScale(self, v):
        self._eye_scale = v
        self.update()
    eyeScale = Property(float, getEyeScale, setEyeScale)

    # Property: mouth_scale
    def getMouthScale(self):
        return self._mouth_scale
    def setMouthScale(self, v):
        self._mouth_scale = v
        self.update()
    mouthScale = Property(float, getMouthScale, setMouthScale)

    def setup_animations(self):
        # head bobbing (bob vertical + small rotation combined via two animations)
        self.bob_anim = QPropertyAnimation(self, b"bob", self)
        self.bob_anim.setStartValue(-4.0)
        self.bob_anim.setKeyValueAt(0.5, 0.0)
        self.bob_anim.setEndValue(-4.0)
        self.bob_anim.setDuration(3200)
        self.bob_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.bob_anim.setLoopCount(-1)
        self.bob_anim.start()

        self.rot_anim = QPropertyAnimation(self, b"rotation", self)
        self.rot_anim.setStartValue(-1.0)
        self.rot_anim.setKeyValueAt(0.5, 1.0)
        self.rot_anim.setEndValue(-1.0)
        self.rot_anim.setDuration(3200)
        self.rot_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.rot_anim.setLoopCount(-1)
        self.rot_anim.start()

        # mouth animation — small scale synced roughly to bob (same duration but different phase)
        self.mouth_anim = QPropertyAnimation(self, b"mouthScale", self)
        self.mouth_anim.setStartValue(1.0)
        self.mouth_anim.setKeyValueAt(0.5, 0.96)
        self.mouth_anim.setEndValue(1.0)
        self.mouth_anim.setDuration(3200)
        self.mouth_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.mouth_anim.setLoopCount(-1)
        self.mouth_anim.start()

        # blinking: schedule blinks at random intervals
        self.blink_timer = QTimer(self)
        self.blink_timer.setSingleShot(True)
        self.blink_timer.timeout.connect(self.do_blink)
        self.schedule_next_blink()

    def schedule_next_blink(self):
        # schedule next blink somewhere between 2.5s and 6.5s
        interval = random.uniform(2.5, 6.5) * 1000
        self.blink_timer.start(int(interval))

    def do_blink(self):
        # two-step quick animation: close then open
        close = QPropertyAnimation(self, b"eyeScale", self)
        close.setStartValue(1.0)
        close.setEndValue(0.12)
        close.setDuration(80)
        open_ = QPropertyAnimation(self, b"eyeScale", self)
        open_.setStartValue(0.12)
        open_.setEndValue(1.0)
        open_.setDuration(120)

        # chain: close then open
        def start_open():
            open_.start()
        close.finished.connect(start_open)

        def finished_all():
            self.schedule_next_blink()
        open_.finished.connect(finished_all)

        close.start()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(0, 0, w, h, QColor("#0f1113"))

        # center frame for the icon
        cx, cy = w // 2, h // 2
        painter.translate(cx, cy + self._bob)  # vertical bob
        painter.rotate(self._rotation)         # slight rotation

        # draw outer shell (rounded rect)
        shell_w, shell_h = 120, 80
        painter.setBrush(QBrush(QColor("#3b3f46")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(-shell_w//2, -shell_h//2, shell_w, shell_h, 18, 18)

        # inner face
        painter.setBrush(QBrush(QColor("#2f3338")))
        painter.drawRoundedRect(-shell_w//2 + 8, -shell_h//2 + 8, shell_w - 16, shell_h - 16, 12, 12)

        # eyes (two rounded rects), animate vertical scale for blink
        eye_w, eye_h = 18, 12
        eye_y = -6
        eye_x_offset = 24
        painter.save()
        # left eye
        painter.translate(-eye_x_offset, eye_y)
        painter.scale(1.0, self._eye_scale)
        painter.setBrush(QBrush(QColor("#bfc6cc")))
        painter.drawRoundedRect(-eye_w//2, -eye_h//2, eye_w, eye_h, 4, 4)
        painter.restore()

        painter.save()
        # right eye
        painter.translate(eye_x_offset, eye_y)
        painter.scale(1.0, self._eye_scale)
        painter.setBrush(QBrush(QColor("#bfc6cc")))
        painter.drawRoundedRect(-eye_w//2, -eye_h//2, eye_w, eye_h, 4, 4)
        painter.restore()

        # mouth group (rectangle with three darker 'teeth' bars)
        painter.save()
        mouth_w, mouth_h = 40, 10
        mouth_y = 22
        # apply small mouth scale on Y (breathe / bop)
        painter.translate(0, mouth_y)
        painter.scale(1.0, self._mouth_scale)
        painter.setBrush(QBrush(QColor("#d7dde2")))
        painter.drawRoundedRect(-mouth_w//2, -mouth_h//2, mouth_w, mouth_h, 3, 3)
        # teeth bars
        painter.setBrush(QBrush(QColor("#3b3f46")))
        bars = [-14,  -2,  10]
        for bx in bars:
            painter.drawRect(bx, -3, 4, 6)
        painter.restore()

def main():
    app = QApplication(sys.argv)
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(20, 20, 20, 20)
    icon = CopilotIcon(size=200)
    layout.addWidget(icon, alignment=Qt.AlignCenter)
    w.setWindowTitle("Copilot-style Animated Icon (PySide6)")
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()