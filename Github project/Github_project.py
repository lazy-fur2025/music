import sys
import time
import numpy as np
import sounddevice as sd
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QLinearGradient,
    QConicalGradient,
    QBrush,
)


class AudioThread(QThread):
    audio_signal = Signal(np.ndarray)
    record_done = Signal(bytes)

    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.record_buffer = []

    def run(self):
        def callback(indata, frames, time, status):
            if any(indata):
                magnitude = np.abs(np.fft.rfft(indata[:, 0]))
                chunks = np.array_split(magnitude, 15)
                self.audio_signal.emit(np.array([np.mean(c) for c in chunks]))
                if self.is_recording:
                    audio_bytes = (indata * 32767).astype(np.int16).tobytes()
                    self.record_buffer.append(audio_bytes)

        with sd.InputStream(
            callback=callback, channels=1, samplerate=16000, blocksize=1024
        ):
            while True:
                self.sleep(1)


class ModernWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(520, 50)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QWidget { border-radius: 15px; }")

        self.lyric_label = QLabel("♪ 点击红点识别，长按红点退出 awa", self)
        self.lyric_label.setGeometry(120, 0, 350, 45)
        self.lyric_label.setStyleSheet("font-size: 13px; color: #00ffff;")
        self.lyric_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lyric_opacity = QGraphicsOpacityEffect(self.lyric_label)
        self.lyric_label.setGraphicsEffect(self.lyric_opacity)

        self.close_btn = QPushButton("", self)
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.move(485, 14)
        self.close_btn.setStyleSheet("background-color: #ff5f56; border-radius: 8px;")
        self.close_btn.pressed.connect(self.on_close_pressed)
        self.close_btn.released.connect(self.on_close_released)

        self.close_progress = 0.0
        self.is_pressing = False
        self.press_start_time = 0

        self.parsed_lyrics = []
        self.current_idx = 0
        self.start_time = 0
        self.is_syncing = False
        self.border_angle = 0
        self.bars = np.zeros(15)
        self.targets = np.zeros(15)

        self.audio_thread = AudioThread()
        self.audio_thread.audio_signal.connect(self.update_bars)
        self.audio_thread.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start(16)

    def on_close_pressed(self):
        self.is_pressing = True
        self.press_start_time = time.time()

    def on_close_released(self):
        duration = time.time() - self.press_start_time
        self.is_pressing = False
        if duration < 0.5:
            self.start_sync_flow()
        self.close_progress = 0.0

    def start_sync_flow(self):
        if self.is_syncing:
            return
        self.is_syncing = True
        self.lyric_label.setText("正在听歌识曲...")
        QTimer.singleShot(3000, self.dummy_recognition)

    def dummy_recognition(self):
        self.lyric_label.setText("识曲成功！开始同步...")
        self.is_syncing = False

    def update_bars(self, v):
        self.targets = np.clip(v * 0.5, 0, 1)

    def on_timer(self):
        self.border_angle = (self.border_angle + 3) % 360
        for i in range(15):
            self.bars[i] += (self.targets[i] - self.bars[i]) * 0.3
        if self.is_pressing:
            elapsed = time.time() - self.press_start_time
            self.close_progress = min(elapsed / 1.5, 1.0)
            if self.close_progress >= 1.0:
                self.close()
        else:
            if self.close_progress > 0:
                self.close_progress -= 0.1
                if self.close_progress < 0:
                    self.close_progress = 0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(40, 40, 40, 230))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 12, 12)
        laser = QConicalGradient(self.rect().center(), self.border_angle)
        laser.setColorAt(0, QColor(0, 255, 255))
        laser.setColorAt(0.1, QColor(0, 255, 255, 0))
        p.setPen(QPen(laser, 2))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -6), 12, 12)
        for i in range(15):
            h = self.bars[i] * 25
            p.setBrush(QColor(0, 255, 200, 200))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(20 + i * 7, 35 - h, 4, h + 1, 2, 2)
        if self.close_progress > 0:
            bar_width = (self.width() - 40) * self.close_progress
            start_x = (self.width() - bar_width) / 2
            red_laser = QLinearGradient(start_x, 0, start_x + bar_width, 0)
            red_laser.setColorAt(0, QColor(255, 0, 0, 50))
            red_laser.setColorAt(0.5, QColor(255, 50, 50, 255))
            red_laser.setColorAt(1, QColor(255, 0, 0, 50))
            p.setBrush(QBrush(red_laser))
            p.drawRoundedRect(QRectF(start_x, 44, bar_width, 3), 1.5, 1.5)
            p.setPen(QPen(QColor(255, 0, 0, 100), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(start_x - 2, 43, bar_width + 4, 5), 2, 2)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.m_pos)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernWindow()
    window.show()
    sys.exit(app.exec())
