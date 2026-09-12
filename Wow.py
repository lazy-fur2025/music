import sys
import time
import re
from urllib.parse import quote
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


class LyricFetchThread(QThread):
    # 用信号把中间状态和最终结果传回主线程，UI 侧只管展示，不用等网络
    status_signal = Signal(str)
    success_signal = Signal(list)  # 解析好的歌词列表 [(时间, 文本), ...]
    error_signal = Signal(str)

    TARGETS = ["PotPlayer", "Chrome", "Edge", "Firefox", "网易云音乐"]

    def run(self):
        try:
            keyword = self._scan_window_title()
            if not keyword:
                self.error_signal.emit("未检测到播放源")
                return
            self.status_signal.emit(f"♪ 匹配中: {keyword}")
            lyrics = self._fetch_netease_lrc(keyword)
            if lyrics:
                self.success_signal.emit(lyrics)
            else:
                self.error_signal.emit("未找到歌词")
        except requests.exceptions.ConnectionError:
            # 最常见的失败原因：NeteaseCloudMusicApi 没启动
            self.error_signal.emit("无法连接歌词服务 (localhost:3000)")
        except requests.exceptions.Timeout:
            self.error_signal.emit("歌词服务响应超时")
        except Exception as exc:
            self.error_signal.emit(f"识曲失败: {exc}")

    def _scan_window_title(self):
        found_kw = ""
        for w in gw.getAllWindows():
            if w.visible and any(t in w.title for t in self.TARGETS) and " - " in w.title:
                found_kw = w.title
                break
        if not found_kw:
            return ""
        for t in self.TARGETS:
            found_kw = found_kw.replace(f" - {t}", "").replace(t, "")
        found_kw = re.sub(r"[\(\[\{].*?[\)\]\}]", "", found_kw)
        found_kw = re.sub(r"\.(mp3|flac|wav|m4a)$", "", found_kw, flags=re.I).strip()
        return found_kw

    def _fetch_netease_lrc(self, keyword):
        # quote() 防止歌名里的 & ? # 空格等字符把 URL 拼坏
        safe_keyword = quote(keyword)
        s_res = requests.get(
            f"http://localhost:3000/cloudsearch?keywords={safe_keyword}", timeout=5
        ).json()
        songs = s_res.get("result", {}).get("songs")
        if not songs:
            return None
        sid = songs[0]["id"]
        l_res = requests.get(
            f"http://localhost:3000/lyric?id={sid}", timeout=5
        ).json()
        raw_lrc = l_res.get("lrc", {}).get("lrc", {}).get("lyric", "")
        if not raw_lrc:
            raw_lrc = l_res.get("lrc", {}).get("lyric", "")

        parsed = []
        for line in raw_lrc.split("\n"):
            if any(x in line for x in ["ar:", "ti:", "al:", "by:"]):
                continue
            m = re.match(r"\[(\d+):(\d+\.\d+)\](.*)", line.strip())
            if not m or not m.group(3).strip():
                continue
            text = m.group(3).strip()
            # 有些歌词文件会把"作词 : xxx"、"作曲：xxx"这类信息也打上时间戳，
            # 这些不是真正要显示的歌词内容，过滤掉避免误显示。
            if re.match(r"^(作词|作曲|编曲|制作人|监制|录音|混音)\s*[:：]", text):
                continue
            parsed.append((int(m.group(1)) * 60 + float(m.group(2)), text))
        return parsed


class AudioThread(QThread):
    audio_signal = Signal(np.ndarray)

    def __init__(self):
        super().__init__()
        self._running = True

    def stop(self):
        # 关窗口时调这个，让 run() 里的循环自然退出，
        # 而不是让 InputStream 和线程一直挂在后台吃 CPU。
        self._running = False
        self.wait(2000)  # 最多等 2 秒让线程收尾，避免主线程被无限期卡住

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
                while self._running:
                    self.msleep(100)  # 更短的检查间隔，stop() 后能更快响应退出
        except Exception as exc:
            # 静默失败等于没给用户任何线索，至少打印出来方便排查
            # （比如麦克风被占用、权限不足、设备不存在等常见情况）
            print(f"[AudioThread] 音频采集异常: {exc}")


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
        
        # --- 新增：歌词微调相关变量 ---
        self.time_offset = 0.0          # 累计微调的时间（秒）
        self.toast_timer = 0.0          # 提示文本倒计时

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

        # 处理关闭进度
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

        # --- 修改：智能歌词滚动与微调提示逻辑 ---
        if self.toast_timer > 0:
            self.toast_timer -= dt
            # 提示结束时，根据当前播放位置刷新正确的歌词
            if self.toast_timer <= 0 and self.parsed_lyrics:
                elapsed = time.time() - self.start_time + self.time_offset
                # 重新计算对应的当前歌词索引
                self.current_idx = 0
                while self.current_idx < len(self.parsed_lyrics) and elapsed >= self.parsed_lyrics[self.current_idx][0]:
                    self.current_idx += 1
                idx = max(0, self.current_idx - 1)
                if idx < len(self.parsed_lyrics):
                    self.lyric_label.setStyleSheet("font-family: 'Microsoft YaHei UI'; font-size: 16px; font-weight: bold; color: white;")
                    self._anim_smooth_text(self.parsed_lyrics[idx][1])
        else:
            # 正常的歌词滚动逻辑（引入了 time_offset 修正值）
            if self.parsed_lyrics and self.current_idx < len(self.parsed_lyrics):
                elapsed = time.time() - self.start_time + self.time_offset
                if elapsed >= self.parsed_lyrics[self.current_idx][0]:
                    self._anim_smooth_text(self.parsed_lyrics[self.current_idx][1])
                    self.current_idx += 1
                    
        self.update()

    # --- 新增：鼠标滚轮微调歌词时间轴 ---
    def wheelEvent(self, event):
        # 仅在已有歌词同步时允许调节
        if not self.parsed_lyrics:
            return
            
        delta = event.angleDelta().y()
        if delta > 0:
            self.time_offset += 0.5  # 歌词前调（让歌词更早出来）
            text = f"⏳ 歌词前调 +0.5s (总计:{self.time_offset:+.1f}s)"
        else:
            self.time_offset -= 0.5  # 歌词后调（让歌词更晚出来）
            text = f"⌛ 歌词后调 -0.5s (总计:{self.time_offset:+.1f}s)"
            
        # 触发视觉提示效果
        self.toast_timer = 1.0  # 提示停留1秒
        self.lyric_label.setStyleSheet("font-family: 'Microsoft YaHei UI'; font-size: 14px; font-weight: bold; color: #00FFFF;")
        self.lyric_label.setText(text)

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
        self.time_offset = 0.0  # 重置微调时间
        self.toast_timer = 0.0
        self.lyric_label.setStyleSheet("font-family: 'Microsoft YaHei UI'; font-size: 16px; font-weight: bold; color: white;")
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

        # 扫描窗口标题和网络请求都挪到后台线程，避免 API 响应慢时把 UI 卡死。
        # 用信号把结果传回来，槽函数里再更新界面。
        self._lyric_thread = LyricFetchThread()
        self._lyric_thread.status_signal.connect(self._on_lyric_status)
        self._lyric_thread.success_signal.connect(self._on_lyric_success)
        self._lyric_thread.error_signal.connect(self._on_lyric_error)
        self._lyric_thread.finished.connect(lambda: setattr(self, "is_syncing", False))
        self._lyric_thread.start()

    def _on_lyric_status(self, text):
        self._anim_smooth_text(text)

    def _on_lyric_success(self, lyrics):
        self.parsed_lyrics = lyrics
        self.start_time = time.time()
        self.current_idx = 0
        self.time_offset = 0.0  # 换歌时清空偏移量
        self.toast_timer = 0.0
        self.lyric_label.setStyleSheet(
            "font-family: 'Microsoft YaHei UI'; font-size: 16px; font-weight: bold; color: white;"
        )
        self._anim_smooth_text("成功")

    def _on_lyric_error(self, message):
        # 之前这里是 except: pass 或者笼统的 "Node.js 接口异常"，
        # 现在把具体原因带出来，方便判断是没开 API 服务还是没搜到歌。
        self._anim_smooth_text(message)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.m_pos)

    def closeEvent(self, event):
        # 不主动停止的话，AudioThread 里的 InputStream 会在后台继续跑，
        # 麦克风指示灯常亮、CPU 也白白被占用。
        if hasattr(self, "audio_thread"):
            self.audio_thread.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernWindow()
    window.show()
    sys.exit(app.exec())