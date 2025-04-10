import sys
import os
import cv2
import numpy as np
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout,
    QHBoxLayout, QSpinBox, QProgressBar, QMessageBox, QCheckBox, QTextEdit, QTabWidget
)
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

class CSSVideoConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSS Video Converter")
        self.setAcceptDrops(True)
        self.video_path = ""
        self.dark_mode = False
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()

        self.label = QLabel("Drop a video or click 'Browse' to choose one")
        self.layout.addWidget(self.label)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_video)
        self.layout.addWidget(browse_btn)

        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("Frames per second:"))
        self.fps_input = QSpinBox()
        self.fps_input.setRange(1, 60)
        self.fps_input.setValue(10)
        fps_layout.addWidget(self.fps_input)
        self.layout.addLayout(fps_layout)

        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Resolution height:"))
        self.height_input = QSpinBox()
        self.height_input.setRange(1, 500)
        self.height_input.setValue(20)
        height_layout.addWidget(self.height_input)
        self.layout.addLayout(height_layout)

        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("Number of threads:"))
        self.thread_input = QSpinBox()
        self.thread_input.setRange(1, 16)
        self.thread_input.setValue(4)
        thread_layout.addWidget(self.thread_input)
        self.layout.addLayout(thread_layout)

        self.convert_btn = QPushButton("Convert to CSS")
        self.convert_btn.clicked.connect(self.convert_to_css)
        self.layout.addWidget(self.convert_btn)

        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)

        self.dark_mode_toggle = QCheckBox("Dark Mode")
        self.dark_mode_toggle.stateChanged.connect(self.toggle_dark_mode)
        self.layout.addWidget(self.dark_mode_toggle)

        self.tabs = QTabWidget()
        self.preview_tab = QTextEdit()
        self.preview_tab.setReadOnly(True)
        self.tabs.addTab(self.preview_tab, "CSS Preview")

        self.html_tab = QTextEdit()
        self.html_tab.setReadOnly(True)
        self.tabs.addTab(self.html_tab, "HTML Preview")

        self.layout.addWidget(self.tabs)

        self.setLayout(self.layout)

    def toggle_dark_mode(self):
        self.dark_mode = self.dark_mode_toggle.isChecked()
        palette = self.palette()
        if self.dark_mode:
            palette.setColor(self.backgroundRole(), Qt.black)
            palette.setColor(self.foregroundRole(), Qt.white)
            self.setStyleSheet("* { color: white; background-color: #222; }")
        else:
            palette.setColor(self.backgroundRole(), Qt.white)
            palette.setColor(self.foregroundRole(), Qt.black)
            self.setStyleSheet("")

    def browse_video(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Video File")
        if file_name:
            self.video_path = file_name
            self.label.setText(f"Selected: {os.path.basename(file_name)}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    self.video_path = file_path
                    self.label.setText(f"Dropped: {os.path.basename(file_path)}")
                    break

    def convert_to_css(self):
        if not self.video_path:
            QMessageBox.warning(self, "Error", "No video selected")
            return

        result_fps = self.fps_input.value()
        result_height = self.height_input.value()
        num_threads = self.thread_input.value()

        cap = cv2.VideoCapture(self.video_path)
        success, frame = cap.read()
        if not success:
            QMessageBox.critical(self, "Error", "Cannot read video")
            return

        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        result_width = int(width * result_height / height)

        nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        video_duration = round(nb_frames / video_fps)
        nb_result_frames = video_duration * result_fps

        css_file = "video.css"
        self.generated_css = ""
        self.generated_css += f"""
#cssVideo {{
    position: sticky;
    top: -1px;
    left: -1px;
    overflow: visible;
    width: 1px;
    height: 1px;
    animation: cssVideo linear {video_duration}s both infinite;
}}

@keyframes cssVideo {{
"""

        def write_css_colors(frame):
            resized = cv2.resize(frame, (result_width, result_height))
            return [f"{x}px {y}px 0 #{r:02x}{g:02x}{b:02x},"
                    for x in range(result_width)
                    for y in range(result_height)
                    for b, g, r in [resized[y, x]]]

        def process_frames(start, end, tid):
            cap_local = cv2.VideoCapture(self.video_path)
            cap_local.set(cv2.CAP_PROP_POS_FRAMES, start)
            for i in range(start, end):
                ret, frame = cap_local.read()
                if not ret:
                    break
                if i % round(nb_frames / nb_result_frames) == 0:
                    pct = i * 100 / nb_frames
                    css_colors = write_css_colors(frame)
                    self.generated_css += f"{pct:.2f}% {{box-shadow: {''.join(css_colors)[:-1]};}}\n"
                progress = int(((i - start) / (end - start)) * 100)
                self.progress_bar.setValue(progress)
            cap_local.release()

        threads = []
        frames_per_thread = nb_frames // num_threads
        for i in range(num_threads):
            start = i * frames_per_thread
            end = (i + 1) * frames_per_thread if i < num_threads - 1 else nb_frames
            t = threading.Thread(target=process_frames, args=(start, end, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.generated_css += "}"

        html_preview = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>CSS Video</title>
    <link rel=\"stylesheet\" href=\"video.css\">
</head>
<body>
    <div style=\"scale: {result_height/10};\" id=\"cssVideo\"></div>
</body>
</html>
"""

        with open(css_file, "w") as f:
            f.write(self.generated_css)

        with open("index.html", "w") as html:
            html.write(html_preview)

        self.preview_tab.setPlainText(self.generated_css)
        self.html_tab.setPlainText(html_preview)
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "Done", "CSS and HTML files generated!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CSSVideoConverter()
    window.resize(600, 600)
    window.show()
    sys.exit(app.exec_())
