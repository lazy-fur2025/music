import sys
import time
import re
import numpy as np
import sounddevice as sd
import requests
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QGraphicsOpacityEffect,
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
    QBrush,
)
from aip import AipSpeech

APP_ID = "122613402"
API_KEY = "55ceHhcq8vTBBKG0usu0q88G"
SECRET_KEY = "IhsTwI87Lso8TbsTpvI7pXkW96EkBPlv"
client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)


class AudioThread(QThread):
    audio_signal = Signal(np.ndarray)

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

        self.lyric_label = QLabel("♪ 点击红点识别，长按红点退出 awa", self)
        self.lyric_label.setGeometry(120, 0, 350, 45)
        self.lyric_label.setStyleSheet("font-size: 13px; color: #00ffff;")
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
        self.lyric_label.setText("正在听歌识曲... (录制 3.5 秒)")
        self.audio_thread.record_buffer = []
        self.audio_thread.is_recording = True
        QTimer.singleShot(3500, self.process_recognition)

    def process_recognition(self):
        self.audio_thread.is_recording = False
        audio_data = b"".join(self.audio_thread.record_buffer)

        res = client.asr(audio_data, "pcm", 16000, {"dev_pid": 1537})
        if res and res["err_no"] == 0:
            keyword = res["result"][0]
            self.lyric_label.setText(f"🔍 搜寻: {keyword}")
            self.fetch_netease_lrc(keyword)
        else:
            self.lyric_label.setText("没听清，离音箱近点试试 awa")
            self.is_syncing = False

    def fetch_netease_lrc(self, kw):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://music.163.com/",
            }

            search_url = "https://music.163.com/api/search/get/web"
            params = {"s": kw, "type": 1, "limit": 1}

            search_res = requests.get(
                search_url, params=params, headers=headers, timeout=5
            ).json()

            if "result" not in search_res or "songs" not in search_res["result"]:
                self.lyric_label.setText(f"未能匹配到歌曲: {kw}")
                self.is_syncing = False
                return

            song = search_res["result"]["songs"][0]
            sid = song["id"]
            s_name = song["name"]
            artist = song["artists"][0]["name"]
            self.lyric_label.setText(f"♪ 正在同步: {s_name} - {artist}")

            lrc_url = f"https://music.163.com/api/song/lyric?id={sid}&lv=1"
            lrc_res = requests.get(lrc_url, headers=headers, timeout=5).json()

            if "lrc" not in lrc_res or "lyric" not in lrc_res["lrc"]:
                self.lyric_label.setText("该歌曲暂无歌词 awa")
                self.is_syncing = False
                return

            lrc_text = lrc_res["lrc"]["lyric"]

            self.parsed_lyrics = []
            pattern = re.compile(r"\[(\d+):(\d+\.\d+)\](.*)")
            for line in lrc_text.split("\n"):
                m = pattern.match(line.strip())
                if m:
                    time_sec = int(m.group(1)) * 60 + float(m.group(2))
                    content = m.group(3).strip()
                    if content:
                        self.parsed_lyrics.append((time_sec, content))

            self.start_time = time.time() - 7.0
            self.current_idx = 0
            self.is_syncing = False

        except Exception as e:
            print(f"DEBUG - 搜歌失败详情: {e}")
            self.lyric_label.setText("网络请求失败，请稍后再试")
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

        if self.parsed_lyrics and self.current_idx < len(self.parsed_lyrics):
            if (time.time() - self.start_time) >= self.parsed_lyrics[self.current_idx][
                0
            ]:
                self.animate_text(self.parsed_lyrics[self.current_idx][1])
                self.current_idx += 1
        self.update()

    def animate_text(self, text):
        f_out = QPropertyAnimation(self.lyric_opacity, b"opacity")
        f_out.setDuration(300)
        f_out.setEndValue(0.0)
        f_in = QPropertyAnimation(self.lyric_opacity, b"opacity")
        f_in.setDuration(300)
        f_in.setEndValue(1.0)
        f_out.finished.connect(lambda: self.lyric_label.setText(text))
        self.group = QSequentialAnimationGroup()
        self.group.addAnimation(f_out)
        self.group.addAnimation(f_in)
        self.group.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(30, 30, 30, 150))
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
            bar_w = (self.width() - 40) * self.close_progress
            start_x = (self.width() - bar_w) / 2
            grad = QLinearGradient(start_x, 0, start_x + bar_w, 0)
            grad.setColorAt(0, QColor(255, 0, 0, 50))
            grad.setColorAt(0.5, QColor(255, 50, 50, 255))
            grad.setColorAt(1, QColor(255, 0, 0, 50))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(start_x, 44, bar_w, 3), 1.5, 1.5)

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
