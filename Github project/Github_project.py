import sys
import time
import re
import pygetwindow as gw
import numpy as np
import sounddevice as sd
import requests
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QGraphicsOpacityEffect,
    QHBoxLayout,
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    QThread,
    Signal,
    QRectF,
    QSequentialAnimationGroup,
    QPropertyAnimation,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QLinearGradient,
    QConicalGradient,
    QRadialGradient,
    QPainterPath,
)


class AudioThread(QThread):
    audio_signal = Signal(np.ndarray)

    def run(self):
        def callback(indata, frames, time_info, status):
            if any(indata):
                magnitude = np.abs(np.fft.rfft(indata[:, 0]))
                chunks = np.array_split(magnitude, 15)
                self.audio_signal.emit(np.array([np.mean(c) for c in chunks]))

        try:
            with sd.InputStream(
                callback=callback, channels=1, samplerate=None, blocksize=1024
            ):
                while True:
                    self.sleep(1)
        except:
            pass


class ModernWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(520, 50)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._init_state()
        self._build_ui()
        self._init_audio()
        self._start_timer()

    def _init_state(self):
        self.close_progress = 0.0
        self.is_pressing = False
        self.press_start_time = 0
        self.close_anim_active = False
        self.close_anim_progress = 0.0
        self.parsed_lyrics = []
        self.current_idx = 0
        self.start_time = 0
        self.is_syncing = False
        self.border_angle = 0.0
        self.bars = np.zeros(15, dtype=float)
        self.targets = np.zeros(15, dtype=float)
        self._last_tick = time.perf_counter()
        self._bg_pulse = 0.0

    def _build_ui(self):
        self.lyric_label = QLabel("点击红色按钮一次开始识曲，长按关闭", self)
        self.lyric_label.setGeometry(120, 0, 320, 45)
        self.lyric_label.setAlignment(Qt.AlignCenter)
        self.lyric_label.setStyleSheet(
            "font-family: 'Microsoft YaHei UI'; font-size: 16px; font-weight: bold; color: white;"
        )
        self.lyric_opacity = QGraphicsOpacityEffect(self.lyric_label)
        self.lyric_label.setGraphicsEffect(self.lyric_opacity)

        self.btn_container = QWidget(self)
        self.btn_container.setGeometry(390, 0, 110, 50)
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 15, 0)
        self.btn_layout.setSpacing(12)
        self.btn_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.reset_btn = QPushButton("", self)
        self.reset_btn.setFixedSize(14, 14)
        self.reset_btn.setStyleSheet(
            "background-color: #FFBD2E; border-radius: 7px; border: none;"
        )
        self.reset_btn.clicked.connect(self.reset_flow)

        self.close_btn = QPushButton("", self)
        self.close_btn.setFixedSize(14, 14)
        self.close_btn.setStyleSheet(
            "background-color: #FF5F56; border-radius: 7px; border: none;"
        )
        self.close_btn.pressed.connect(self.on_close_pressed)
        self.close_btn.released.connect(self.on_close_released)

        self.btn_layout.addWidget(self.reset_btn)
        self.btn_layout.addWidget(self.close_btn)

    def _init_audio(self):
        self.audio_thread = AudioThread()
        self.audio_thread.audio_signal.connect(
            lambda v: setattr(self, "targets", np.clip(v.astype(float) * 0.4, 0.0, 1.0))
        )
        self.audio_thread.start()

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start(16)

    def on_timer(self):
        now = time.perf_counter()
        dt = min(now - self._last_tick, 0.05)
        self._last_tick = now

        if self.is_pressing and not self.close_anim_active:
            self.close_progress = min(self.close_progress + dt / 0.8, 1.0)
            if self.close_progress >= 1.0:
                self.close_anim_active = True
        elif not self.close_anim_active:
            self.close_progress = max(0, self.close_progress - dt * 2.0)

        if self.close_anim_active:
            self.close_anim_progress += dt * 3.5
            if self.close_anim_progress >= 1.2:
                self.close()

        self.border_angle = (self.border_angle + 100.0 * dt) % 360.0
        self._bg_pulse += dt * 1.5
        for i in range(15):
            f = (
                (1.0 - np.exp(-25.0 * dt))
                if self.targets[i] > self.bars[i]
                else (1.0 - np.exp(-6.0 * dt))
            )
            self.bars[i] += (self.targets[i] - self.bars[i]) * f

        if self.parsed_lyrics and self.current_idx < len(self.parsed_lyrics):
            if (time.time() - self.start_time) >= self.parsed_lyrics[self.current_idx][
                0
            ]:
                self._anim_smooth_text(self.parsed_lyrics[self.current_idx][1])
                self.current_idx += 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.fillPath(self._get_round_path(rect, 14), QColor(20, 20, 26, 230))

        for i in range(15):
            val = (self.bars[i] ** 0.7) * 15 + 2
            r = QRectF(25 + i * 8, 42 - val, 4, val)
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, QColor(0, 255, 255))
            g.setColorAt(1, QColor(0, 100, 255, 50))
            p.fillRect(r, g)

        path = self._get_round_path(rect, 13)

        outer = QConicalGradient(rect.center(), self.border_angle)
        outer.setColorAt(0.0, QColor(0, 255, 255, 80))
        outer.setColorAt(0.12, QColor(0, 255, 255, 0))
        outer.setColorAt(0.5, QColor(255, 100, 200, 80))
        outer.setColorAt(0.62, QColor(255, 100, 200, 0))
        outer.setColorAt(1.0, QColor(0, 255, 255, 80))
        p.setPen(QPen(outer, 6))
        p.drawPath(path)

        inner = QConicalGradient(rect.center(), self.border_angle)
        inner.setColorAt(0.0, QColor(0, 255, 255, 255))
        inner.setColorAt(0.06, QColor(180, 80, 255, 220))
        inner.setColorAt(0.14, QColor(0, 255, 255, 0))
        inner.setColorAt(0.48, QColor(255, 80, 180, 220))
        inner.setColorAt(0.56, QColor(180, 80, 255, 220))
        inner.setColorAt(0.64, QColor(0, 255, 255, 0))
        inner.setColorAt(1.0, QColor(0, 255, 255, 255))
        p.setPen(QPen(inner, 2.5))
        p.drawPath(path)

        self._draw_breathing_lights(p)

        if self.close_anim_active:
            w, h, prog = self.width(), self.height(), self.close_anim_progress
            p.setPen(Qt.NoPen)

            x1 = prog * (w + 120) - 80
            p.setBrush(QColor(255, 20, 20, 200))
            path1 = QPainterPath()
            path1.moveTo(x1, 0)
            path1.lineTo(x1 + 70, 0)
            path1.lineTo(x1 + 30, h)
            path1.lineTo(x1 - 40, h)
            p.drawPath(path1)

            x2 = w - (prog * (w + 120)) + 80
            p.setBrush(QColor(255, 80, 80, 240))
            path2 = QPainterPath()
            path2.moveTo(x2, 0)
            path2.lineTo(x2 - 50, 0)
            path2.lineTo(x2 - 90, h)
            path2.lineTo(x2 - 40, h)
            p.drawPath(path2)

        elif self.close_progress > 0:
            center = self.close_btn.mapTo(self, self.close_btn.rect().center())
            p.setPen(QPen(QColor(255, 60, 60, 150), 2))
            r = 7 + 10 * self.close_progress
            p.drawEllipse(center, r, r)

    def _anim_smooth_text(self, text):
        if hasattr(self, "_anim") and self._anim:
            self._anim.stop()
        f_out = QPropertyAnimation(self.lyric_opacity, b"opacity")
        f_out.setDuration(150)
        f_out.setStartValue(self.lyric_opacity.opacity())
        f_out.setEndValue(0.0)
        f_in = QPropertyAnimation(self.lyric_opacity, b"opacity")
        f_in.setDuration(200)
        f_in.setStartValue(0.0)
        f_in.setEndValue(1.0)
        f_out.finished.connect(lambda: self.lyric_label.setText(text))
        self._anim = QSequentialAnimationGroup()
        self._anim.addAnimation(f_out)
        self._anim.addAnimation(f_in)
        self._anim.start()

    def _get_round_path(self, rect, radius):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path

    def _draw_breathing_lights(self, p):
        for btn, color in [
            (self.reset_btn, QColor(255, 189, 46)),
            (self.close_btn, QColor(255, 95, 86)),
        ]:
            center = btn.mapTo(self, btn.rect().center())
            pulse = 0.5 + 0.5 * np.sin(
                self._bg_pulse + (0 if btn == self.reset_btn else 3.14)
            )
            g = QRadialGradient(center.x(), center.y(), 10 + pulse * 6)
            g.setColorAt(
                0, QColor(color.red(), color.green(), color.blue(), int(130 * pulse))
            )
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillPath(self._get_circle_path(center.x(), center.y(), 10 + pulse * 6), g)

    def _get_circle_path(self, x, y, r):
        path = QPainterPath()
        path.addEllipse(x - r, y - r, r * 2, r * 2)
        return path

    def reset_flow(self):
        self.parsed_lyrics = []
        self.current_idx = 0
        self._anim_smooth_text("已经终止当前识曲")

    def on_close_pressed(self):
        self.is_pressing = True
        self.press_start_time = time.perf_counter()

    def on_close_released(self):
        if (time.perf_counter() - self.press_start_time) < 0.4:
            self.start_sync_flow()
        self.is_pressing = False

    def start_sync_flow(self):
        if self.is_syncing:
            return
        self.is_syncing = True
        self._anim_smooth_text("🔍 正在扫描...")
        QTimer.singleShot(100, self._perform_scan)

    def _perform_scan(self):
        targets = ["PotPlayer", "Chrome", "Edge", "Firefox", "网易云音乐"]
        found_kw = ""
        try:
            for w in gw.getAllWindows():
                if (
                    w.visible
                    and any(t in w.title for t in targets)
                    and " - " in w.title
                ):
                    found_kw = w.title
                    break
            if found_kw:
                for t in targets:
                    found_kw = found_kw.replace(f" - {t}", "").replace(t, "")
                found_kw = re.sub(r"[\(\[\{].*?[\)\]\}]", "", found_kw)
                found_kw = re.sub(
                    r"\.(mp3|flac|wav|m4a)$", "", found_kw, flags=re.I
                ).strip()
                self._anim_smooth_text(f"♪ 匹配中: {found_kw}")
                self.fetch_netease_lrc(found_kw)
            else:
                self._anim_smooth_text("未检测到播放源")
                self.is_syncing = False
        except:
            self.is_syncing = False

    def fetch_netease_lrc(self, keyword):
        try:
            s_res = requests.get(
                f"http://localhost:3000/cloudsearch?keywords={keyword}", timeout=3
            ).json()
            sid = s_res["result"]["songs"][0]["id"]
            l_res = requests.get(
                f"http://localhost:3000/lyric?id={sid}", timeout=3
            ).json()
            raw_lrc = l_res.get("lrc", {}).get("lyric", "")
            self.parsed_lyrics = []
            for line in raw_lrc.split("\n"):
                if any(x in line for x in ["ar:", "ti:", "al:", "by:"]):
                    continue
                m = re.match(r"\[(\d+):(\d+\.\d+)\](.*)", line.strip())
                if m and m.group(3).strip():
                    self.parsed_lyrics.append(
                        (int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip())
                    )
            self.start_time = time.time()
            self.current_idx = 0
            self._anim_smooth_text("成功")
        except:
            self._anim_smooth_text("Node.js 接口异常")
        finally:
            self.is_syncing = False

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
