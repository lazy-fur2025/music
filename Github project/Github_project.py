import sys
import numpy as np  
import sounddevice as sd  
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve, Property, QSequentialAnimationGroup, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QConicalGradient

class AudioThread(QThread):
    audio_signal = Signal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.n_bars = 15                                                                  #这里是存放音频柱的数量。

    def run(self):
        def callback(indata, frames, time, status):
            if any(indata):
                magnitude = np.abs(np.fft.rfft(indata[:, 0]))                            #对音频数据进行快速傅里叶变换，获取频谱的幅度信息。
                chunks = np.array_split(magnitude, self.n_bars)                          #将频率分成若干块，让音乐有层次感。
                values = np.array([np.mean(chunk) for chunk in chunks])                  #这里是发掘音频柱的高度。
                self.audio_signal.emit(values)                                           #这里在不断更新数据，保证柱子能跟着音乐跳动起来！

        with sd.InputStream(callback=callback, channels=1, samplerate=44100, blocksize=1024):  
            while True: self.sleep(1)                                                    #这里在监听麦克风的声音

class ModernWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("窗口")
        self.resize(520, 45)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
       
        # 基础样式设置
        self.bg_color = "rgba(40, 40, 40, 230)"
        self.setStyleSheet(f"""
            QWidget {{
                background: {self.bg_color};
                border-radius: 15px;
            }}
            QLabel {{ background: none; color: white; }}
        """)

        self.lyric_label = QLabel("♪ 正在加载歌词...", self)
        self.lyric_label.setGeometry(120, 0, 350, 45)
        self.lyric_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lyric_label.setStyleSheet("font-size: 13px; color: #ddd;")
        
        # --- ### 【终极修复】让鼠标点击穿透歌词标签，从而可以拖动窗口 ### ---
        self.lyric_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.lyric_opacity = QGraphicsOpacityEffect(self.lyric_label)
        self.lyric_label.setGraphicsEffect(self.lyric_opacity)

        self.lyrics = ["在夜半三更过天桥", "从来不敢回头看", "白日里是车水马龙", "此时脚下是忘川"]
        self.lyric_index = 0

        self.close_btn = QPushButton("", self)
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.move(485, 14)
        self.close_btn.setStyleSheet("background-color: #ff5f56; border-radius: 8px;")
        self.close_btn.clicked.connect(self.close)
        
        self.btn_opacity_effect = QGraphicsOpacityEffect(self.close_btn)
        self.close_btn.setGraphicsEffect(self.btn_opacity_effect)

        self.border_angle = 0  # 激光旋转的角度
        self.n_bars = 15
        self.bar_values = np.zeros(self.n_bars) 
        self.target_values = np.zeros(self.n_bars) 

        self.init_animations()                                                             #初始化动画，在这里，我们设置了按钮的呼吸灯动画和歌词切换的动画效果！
        
        self.audio_thread = AudioThread()
        self.audio_thread.audio_signal.connect(self.update_audio_data)
        self.audio_thread.start()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.smooth_animation)
        self.refresh_timer.start(16) # 60FPS

        self.drag_position = QPoint()

    def update_audio_data(self, values):
        self.target_values = np.clip(values * 0.5, 0, 1)

    def smooth_animation(self):
        # 旋转激光角度：每帧转3度，数值越大转得越快
        self.border_angle = (self.border_angle + 3) % 360
        
        for i in range(self.n_bars):
            if self.target_values[i] > self.bar_values[i]:
                self.bar_values[i] += (self.target_values[i] - self.bar_values[i]) * 0.4
            else:
                self.bar_values[i] -= (self.bar_values[i] - self.target_values[i]) * 0.15
        self.update() 

    def init_animations(self):
        self.breath_anim = QPropertyAnimation(self.btn_opacity_effect, b"opacity")        #创建一个属性动画，作用于按钮的透明度。
        self.breath_anim.setDuration(1500)                                                #设置动画持续时间为1.5秒。
        self.breath_anim.setStartValue(0.4)                                               #设置动画的起始值为0.4（半透明）。
        self.breath_anim.setEndValue(1.0)                                                 #设置动画的结束值为1.0（完全不透明）。
        self.breath_anim.setEasingCurve(QEasingCurve.Type.InOutSine)                      
        self.breath_anim.setLoopCount(-1)                                                 #无限循环。
        self.breath_anim.setDirection(QPropertyAnimation.Direction.Backward)              #往返运动。
        self.breath_anim.start()

        self.lyric_timer = QTimer(self)
        self.lyric_timer.timeout.connect(self.animate_lyric_change)                       #看，在这里切换歌词。
        self.lyric_timer.start(3000)

    def animate_lyric_change(self):
        fade_out = QPropertyAnimation(self.lyric_opacity, b"opacity")
        fade_out.setDuration(500)                                                         #设置动画持续时间为0.5秒。
        fade_out.setStartValue(1.0)                                                       #让字体完全显现出来
        fade_out.setEndValue(0.0)                                                         #这里就算字体淡出了哦。

        fade_in = QPropertyAnimation(self.lyric_opacity, b"opacity")
        fade_in.setDuration(500) 
        fade_in.setStartValue(0.0)                                                        #让字体突然消失，耶！没错，然后再显现出来！！
        fade_in.setEndValue(1.0)

        fade_out.finished.connect(self.update_lyric_text)                                 
        
        self.group = QSequentialAnimationGroup()   
        self.group.addAnimation(fade_out)                                                 #将淡出动画添加到动画组中。
        self.group.addAnimation(fade_in)                                                  #先淡出旧歌词，然后淡入新歌词。
        self.group.start()                                                                #动画，启动！！！！等不及辣！！！

    def update_lyric_text(self):                                                          #切换到下一句歌词。
        self.lyric_label.setText(self.lyrics[self.lyric_index])                           
        self.lyric_index = (self.lyric_index + 1) % len(self.lyrics)                      

    def paintEvent(self, event):                                                          #这里是美化边框的地方啦！
        painter = QPainter(self)                                                          
        painter.setRenderHint(QPainter.Antialiasing)                                      

        # --- ### 激光流光边框逻辑 ### ---
        # 我们创建一个旋转的锥形渐变。
        # 想象一道电光蓝在黑暗中扫过边框。
        laser_grad = QConicalGradient(self.rect().center(), self.border_angle)
        laser_grad.setColorAt(0, QColor(0, 255, 255, 255))   # 极亮电光蓝（激光头）
        laser_grad.setColorAt(0.1, QColor(0, 255, 255, 0))   # 迅速淡化到透明（激光尾巴）
        laser_grad.setColorAt(0.9, QColor(0, 255, 255, 0))   # 大部分区域保持透明
        laser_grad.setColorAt(1, QColor(0, 255, 255, 255))   # 回到起点

        # 使用这个渐变色笔刷
        laser_pen = QPen(laser_grad, 2) # 2像素宽的激光
        painter.setPen(laser_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)

        # --- ### 音频柱逻辑 ### ---
        bar_width = 4
        spacing = 3
        max_h = 25
        base_y = 35
        for i in range(self.n_bars):
            h = self.bar_values[i] * max_h
            grad = QLinearGradient(0, base_y, 0, base_y - max_h)
            grad.setColorAt(0, QColor(0, 180, 255, 150))
            grad.setColorAt(1, QColor(0, 255, 200, 255))
            painter.setBrush(grad)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(20 + i*(bar_width+spacing), base_y - h, bar_width, h + 1, 2, 2)

    def mousePressEvent(self, event):                                                     #这里是可以让你拖动窗口的地方哦！
        if event.button() == Qt.LeftButton:                                               
            self.drag_position = event.globalPosition().toPoint() - self.pos()            
            event.accept()                                                                

    def mouseMoveEvent(self, event):                                                      #拖动窗口。
        if event.buttons() & Qt.LeftButton:                                               
            self.move(event.globalPosition().toPoint() - self.drag_position)              
            event.accept()                                                                #接受接受。awa

if __name__ == "__main__":                                                                #入口。
    app = QApplication(sys.argv)                                                          
    demo = ModernWindow()                                                                 
    demo.show()                                                                           
    sys.exit(app.exec())