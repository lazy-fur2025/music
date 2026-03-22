import sys
import numpy as np  
import sounddevice as sd  
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve, Property, QSequentialAnimationGroup, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient

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
       
        self.bg_color = "rgba(40, 40, 40, 230)"
        self.setStyleSheet(f"""
            QWidget {{
                background: {self.bg_color};
                border-radius: 12px;
            }}
            QLabel {{ background: none; color: white; }}
        """)

        self.lyric_label = QLabel("♪ 正在加载歌词...", self)
        self.lyric_label.setGeometry(120, 0, 350, 45)
        self.lyric_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lyric_label.setStyleSheet("font-size: 13px; color: #ddd;")
        
        self.lyric_opacity = QGraphicsOpacityEffect(self.lyric_label)
        self.lyric_label.setGraphicsEffect(self.lyric_opacity)

        self.lyrics = ["我们生来孤独", "却假装彼此需要", "时间把一切磨平"]
        self.lyric_index = 0

        self.close_btn = QPushButton("", self)
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.move(485, 14)
        self.close_btn.setStyleSheet("background-color: #ff5f56; border-radius: 8px;")
        self.close_btn.clicked.connect(self.close)
        
        self.btn_opacity_effect = QGraphicsOpacityEffect(self.close_btn)
        self.close_btn.setGraphicsEffect(self.btn_opacity_effect)

        # --- ### 【新增】可视化相关的数据初始化 ### ---
        self.n_bars = 15
        self.bar_values = np.zeros(self.n_bars) # 能量柱的当前高度
        self.target_values = np.zeros(self.n_bars) # 能量柱的目标高度

        self.init_animations()                                                             #初始化动画，在这里，我们设置了按钮的呼吸灯动画和歌词切换的动画效果！
        
        # ### 【新增】启动音频监听和刷新定时器 ###
        self.audio_thread = AudioThread()
        self.audio_thread.audio_signal.connect(self.update_audio_data)
        self.audio_thread.start()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.smooth_animation)
        self.refresh_timer.start(16) # 大约60帧每秒，丝滑入扣！

        self.drag_position = QPoint()

    # --- ### 【新增】两个处理动画平滑的方法 ### ---
    def update_audio_data(self, values):
        self.target_values = np.clip(values * 0.5, 0, 1)

    def smooth_animation(self):
        # 这个逻辑让柱子上升快、下降慢，产生一种“重力感”
        for i in range(self.n_bars):
            if self.target_values[i] > self.bar_values[i]:
                self.bar_values[i] += (self.target_values[i] - self.bar_values[i]) * 0.4
            else:
                self.bar_values[i] -= (self.bar_values[i] - self.target_values[i]) * 0.15
        self.update() # 强制刷新界面，触发 paintEvent

    def init_animations(self):
        self.breath_anim = QPropertyAnimation(self.btn_opacity_effect, b"opacity")        #创建一个属性动画，作用于按钮的透明度。
        self.breath_anim.setDuration(1500)                                                #设置动画持续时间为1.5秒。
        self.breath_anim.setStartValue(0.4)                                               #设置动画的起始值为0.4（半透明）。
        self.breath_anim.setEndValue(1.0)                                                 #设置动画的结束值为1.0（完全不透明）。
        self.breath_anim.setEasingCurve(QEasingCurve.Type.InOutSine)                      #setEasingCurve方法设置动画的缓动曲线，这里使用了InOutSine曲线，使动画在开始和结束时都比较平滑。
        self.breath_anim.setLoopCount(-1)                                                 #无限循环。
        self.breath_anim.setDirection(QPropertyAnimation.Direction.Backward)              #往返运动。
        self.breath_anim.start()

        #这里是切换歌词的地方哦。
        self.lyric_timer = QTimer(self)
        self.lyric_timer.timeout.connect(self.animate_lyric_change)                       #看，在这里切换歌词。
        self.lyric_timer.start(3000)

    def animate_lyric_change(self):
        #这里实现淡入淡出的歌词效果。
        fade_out = QPropertyAnimation(self.lyric_opacity, b"opacity")
        fade_out.setDuration(500)                                                         #设置动画持续时间为0.5秒。
        fade_out.setStartValue(1.0)                                                       #让字体完全显现出来
        fade_out.setEndValue(0.0)                                                         #这里就算字体淡出了哦。

        fade_in = QPropertyAnimation(self.lyric_opacity, b"opacity")
        fade_in.setDuration(500) 
        fade_in.setStartValue(0.0)                                                        #让字体突然消失，耶！没错，然后再显现出来！！
        fade_in.setEndValue(1.0)

        fade_out.finished.connect(self.update_lyric_text)                                 #当淡出动画完成后，调用update_lyric_text方法更新歌词文本。（哇哦，果然AI的力量无与伦比）
        
        self.group = QSequentialAnimationGroup()   
        self.group.addAnimation(fade_out)                                                 #将淡出动画添加到动画组中。
        self.group.addAnimation(fade_in)                                                  #将淡入动画添加到动画组中，没错！优秀的你一定能猜到，这样就形成了一个连续的动画序列，先淡出旧歌词，然后淡入新歌词。
        self.group.start()                                                                #动画，启动！！！！等不及辣！！！

    def update_lyric_text(self):                                                          #这个方法就是用来更新歌词文本的哦，每次调用都会切换到下一句歌词。
        self.lyric_label.setText(self.lyrics[self.lyric_index])                           #根据索引获取当前歌词并设置到标签上，这样就可以实现歌词的切换了。
        self.lyric_index = (self.lyric_index + 1) % len(self.lyrics)                      #更新索引，确保它在歌词列表的范围内循环，这样就可以不断地切换歌词了哦！

    def paintEvent(self, event):                                                          #这里是美化边框的地方啦，我们接着前进吧！
        painter = QPainter(self)                                                          #创建一个QPainter对象，用于在窗口上进行绘制。
        painter.setRenderHint(QPainter.Antialiasing)                                      #使用抗锯齿，使绘制的边框更加平滑。

        # --- ### 【新增】绘制音频能量柱的部分 ### ---
        bar_width = 4
        spacing = 3
        max_h = 25
        base_y = 35
        for i in range(self.n_bars):
            h = self.bar_values[i] * max_h
            # 画一个好看的渐变色
            grad = QLinearGradient(0, base_y, 0, base_y - max_h)
            grad.setColorAt(0, QColor(0, 180, 255, 150))
            grad.setColorAt(1, QColor(0, 255, 200, 255))
            painter.setBrush(grad)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(20 + i*(bar_width+spacing), base_y - h, bar_width, h + 1, 2, 2)

        painter.setBrush(Qt.NoBrush) # 记得把笔刷重置，不然会影响边框绘制
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))                                #设置画笔颜色为白色，透明度为30，宽度为1，来，让我们一起绘制出一个淡淡的边框吧！
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)               #绘制一个圆角矩形作为窗口的边框，调整矩形的大小以适应窗口，并设置圆角半径为12。

    def mousePressEvent(self, event):                                                     #这里是可以让你拖动窗口的地方哦，试试看吧！
        if event.button() == Qt.LeftButton:                                               #当鼠标左键按下时，记录下鼠标相对于窗口的位置，这样我们就可以在鼠标移动时根据这个位置来移动窗口了，一起动起来吧！
            self.drag_position = event.globalPosition().toPoint() - self.pos()            #记录鼠标相对于窗口的位置。
            event.accept()                                                                #接受事件，表示我们已经处理了这个鼠标按下事件，这样就不会被其他组件或系统处理了哦。

    def mouseMoveEvent(self, event):                                                      #当鼠标移动时，如果左键仍然按下，我们就根据之前记录的位置来移动窗口，这样就可以实现拖动窗口的效果了，试试看吧。
        if event.buttons() & Qt.LeftButton:                                               #看来你的鼠标左键还在按着呢，我们继续移动吧！
            self.move(event.globalPosition().toPoint() - self.drag_position)              #接着计算窗口位置，我不信你不松手了！
            event.accept()                                                                #接受接受。awa

if __name__ == "__main__":                                                                #这里就是入口了，你不关闭它，它就赖你的窗口不走了。
    app = QApplication(sys.argv)                                                          #这是基础。
    demo = ModernWindow()                                                                 #这里包含了我们一起创建的窗口。
    demo.show()                                                                           #来吧，展示窗口，一起在回顾我们的努力吧。
    sys.exit(app.exec())                                                                  #这是个循环，只有你关闭它，它才会结束。