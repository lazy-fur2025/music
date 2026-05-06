# 🎵 识曲窗口

这是我的第一个个人项目 🎉  
一个**带有识曲功能的小窗口程序**，可以识别正在播放的音乐并获取相关信息（如歌曲名、歌词等）。

项目整体偏向练手性质，但已经可以完整运行和使用，欢迎尝试、反馈和改进想法。

---

## ✨ 功能介绍

- 🎧 一键开始识曲
- 📄 获取歌曲信息与歌词（基于 NeteaseCloudMusicApi）
- 🪟 小窗口交互界面
- 🔄 支持重置状态后继续识别新歌曲

> ⚠️ 说明：  
> - **红色按钮**：开始识曲（⚠️ 不要长按，长按会直接终止程序）  
> - **黄色按钮**：重置状态，用于准备识别下一首歌（不是最小化）

---

## 🧩 运行环境要求

- **Python**：推荐 `Python 3.11`（或其他 `3.1x` 版本）
- **Node.js**：用于运行 `NeteaseCloudMusicApi`
- **操作系统**：Windows（目前主要在 Windows 下测试）

---

## 📦 安装与使用

### 1️⃣ 克隆项目

```bash
git clone https://github.com/lazy-fur2025/music.git
cd music\Music    #因为是个嵌套文件夹，可能核心文件需要进一级锁定。
```
---

### 2️⃣ 创建虚拟环境（推荐）

```bash
python -m venv venv
```
激活虚拟环境（Windows）：
```bash
venv\Scripts\activate
```
macOS / Linux：
```bash
source venv/bin/activate
```

---

### 3️⃣ 安装 Python 依赖

```bash
#建议更新一下pip版本以防万一。
python -m pip install --upgrade pip
pip install -r requirements.txt
```
---

### 4️⃣ 启动 Node.js 服务（用于获取歌词）

```bash
npx NeteaseCloudMusicApi
```

---

### 5️⃣ 启动项目

```bash
python Wow.py
```

---

## 📬 联系手段

如果你发现任何bug或其他想法，如果是一些原则性问题，一定一定（求你了QmQ）要联系我即刻改正。
其实你要是想发邮箱对我发牢骚的话，也不是不行，就是我看邮箱的频率低到离谱（但是不会不看）。
呃，如果你通过外网联系我，我可能回复频率更低（因为我只用AI工具awa）。

- GitHub Issues: https://github.com/lazy-fur2025/music/issues
- Email: megalovaina@163.com

---
