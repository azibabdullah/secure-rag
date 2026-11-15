from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget, QGraphicsOpacityEffect,
    QProgressBar, QCheckBox, QSizePolicy,
)

STYLE = """
QWidget { color: #242424; font-family: "Segoe UI"; font-size: 14px; }
QWidget#window, QWidget#conversation, QWidget#canvas { background: #ffffff; }
QFrame#sidebar { background: #f7f7f7; border-right: 1px solid #eeeeee; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 18px; font-weight: 600; }
QLabel#title { font-size: 30px; font-weight: 500; }
QLabel#muted { color: #777777; font-size: 12px; }
QLabel#eyebrow { color: #717171; font-size: 12px; }
QLabel#notice { background: #f7f7f7; border: 1px solid #e6e6e6; border-radius: 12px; padding: 12px; }
QLabel#notice[warning="true"] { background: #fff8f5; border-color: #e8d3c9; color: #773d29; }
QPushButton { background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 9px 12px; }
QFrame#sidebar QPushButton { text-align: left; }
QPushButton:hover { background: #ebebeb; }
QPushButton:pressed { background: #dddddd; }
QPushButton:disabled { color: #aaaaaa; }
QPushButton#primary { background: #252525; color: #ffffff; border-radius: 16px; padding: 8px 16px; font-weight: 600; }
QPushButton#primary:hover { background: #444444; }
QPushButton#primary:disabled { background: #e6e6e6; color: #9a9a9a; }
QFrame#composer { background: #fafafa; border: 1px solid #dedede; border-radius: 22px; }
QPlainTextEdit { background: transparent; border: none; padding: 4px; selection-background-color: #dedede; }
QComboBox { background: transparent; border: 1px solid #e6e6e6; border-radius: 8px; padding: 7px 12px; }
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #eeeeee; color: #242424; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 11px 8px; margin: 2px 0; border-radius: 8px; }
QListWidget::item:selected { background: #e9e9e9; color: #222222; }
QListWidget::item:hover { background: #efefef; }
QFrame#userMessage { background: #f1f1f1; border: none; border-radius: 18px; }
QFrame#assistantMessage { background: transparent; border: none; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 0; }
QScrollBar::handle:vertical { background: #d5d5d5; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #eeeeee; border: none; border-radius: 1px; max-height: 2px; }
QProgressBar::chunk { background: #777777; }
QDialog { background: #ffffff; }
"""


def label(text, name=None):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(True)
    if name:
        item.setObjectName(name)
    return item


class Composer(QPlainTextEdit):
    send = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send.emit()
        else:
            super().keyPressEvent(event)


class Signals(QObject):
    completed = pyqtSignal(str, object, object)
    failed = pyqtSignal(str)


class MainWindow(QWidget):
    def __init__(self, backend_factory=None):
        super().__init__()
        self.setObjectName('window')
        self.setStyleSheet(STYLE)
        self.setWindowTitle('SecureRAG · Local workspace')
        self.resize(1180, 820)
        self.setMinimumSize(850, 640)
        self.setAcceptDrops(True)
        self.busy = False
        self.last_events = []
        self.active_model = ''
        self.animations = []
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.signals = Signals()
        self.signals.completed.connect(self.on_completed)
        self.signals.failed.connect(self.on_failed)
        self.build_ui()
        if backend_factory is None:
            def backend_factory():
                from src.rag.pipeline import SecureRAG
                return SecureRAG()
        self.backend_future = self.pool.submit(backend_factory)
        self.submit('snapshot')

    def button(self, text, slot, primary=False):
        result = QPushButton(text)
        result.clicked.connect(slot)
        if primary:
            result.setObjectName('primary')
        return result

    def build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setMinimumWidth(0)
        self.sidebar.setMaximumWidth(248)
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(16, 24, 16, 18)
        side.setSpacing(8)
        side.addWidget(label('SecureRAG', 'brand'))
        side.addSpacing(16)
        self.new_button = self.button('+   New conversation', self.clear_chat)
        self.new_button.setToolTip('Clear the current transcript')
        side.addWidget(self.new_button)
        self.upload_button = self.button('+   Add document', self.upload)
        side.addWidget(self.upload_button)
        side.addSpacing(24)
        side.addWidget(label('Documents', 'eyebrow'))
        self.documents = QListWidget()
        self.documents.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.documents.currentItemChanged.connect(self.selection_changed)
        side.addWidget(self.documents, 1)
        self.summary_button = self.button('Summarize document', self.summarize)
        self.remove_button = self.button('Remove document', self.remove_selected)
        side.addWidget(self.summary_button)
        side.addWidget(self.remove_button)
        self.events_button = self.button('Security activity', self.show_events)
        side.addWidget(self.events_button)
        self.settings_button = self.button('Settings', self.show_settings)
        side.addWidget(self.settings_button)
        root.addWidget(self.sidebar)

        self.settings_dialog = QDialog(self)
        self.settings_dialog.setWindowTitle('Settings')
        self.settings_dialog.setMinimumWidth(400)
        settings = QVBoxLayout(self.settings_dialog)
        settings.setContentsMargins(24, 24, 24, 24)
        settings.setSpacing(16)
        settings.addWidget(label('Local model', 'brand'))
        settings.addWidget(label('Connect to a model installed in Ollama.', 'muted'))
        self.model = QComboBox()
        settings.addWidget(self.model)
        controls = QHBoxLayout()
        self.connect_button = self.button('Refresh models', lambda: self.submit('available_models'))
        self.use_model_button = self.button('Connect', self.select_model, True)
        controls.addWidget(self.connect_button)
        controls.addWidget(self.use_model_button)
        settings.addLayout(controls)
        self.settings_status = label('', 'muted')
        settings.addWidget(self.settings_status)
        self.motion = QCheckBox('Reduce motion')
        settings.addWidget(self.motion)
        settings.addWidget(self.button('Done', self.settings_dialog.accept))

        main = QVBoxLayout()
        main.setContentsMargins(24, 16, 24, 18)
        main.setSpacing(12)
        top = QHBoxLayout()
        self.sidebar_button = self.button('', self.toggle_sidebar)
        icon = QPixmap(40, 40)
        icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#555555'), 2))
        painter.drawRoundedRect(5, 7, 30, 26, 4, 4)
        painter.drawLine(15, 7, 15, 33)
        painter.end()
        self.sidebar_button.setIcon(QIcon(icon))
        self.sidebar_button.setIconSize(QSize(20, 20))
        self.sidebar_button.setFixedSize(36, 36)
        self.sidebar_button.setToolTip('Show or hide sidebar')
        self.sidebar_button.setAccessibleName('Toggle sidebar')
        top.addWidget(self.sidebar_button)
        top.addStretch()
        self.mode = QComboBox()
        self.mode.addItem('General chat', 'chat')
        self.mode.addItem('Ask documents', 'documents')
        self.mode.currentIndexChanged.connect(self.selection_changed)
        top.addWidget(self.mode)
        main.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        canvas = QWidget()
        canvas.setObjectName('canvas')
        centered = QHBoxLayout(canvas)
        centered.setContentsMargins(0, 0, 0, 0)
        centered.addStretch()
        self.messages_widget = QWidget()
        self.messages_widget.setObjectName('conversation')
        self.messages_widget.setMaximumWidth(760)
        self.messages_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 36, 0, 20)
        self.messages_layout.setSpacing(28)
        self.messages_layout.addStretch()
        centered.addWidget(self.messages_widget, 1)
        centered.addStretch()
        self.scroll.setWidget(canvas)
        main.addWidget(self.scroll, 1)
        self.empty = QWidget()
        welcome = QVBoxLayout(self.empty)
        welcome.setContentsMargins(10, 85, 10, 60)
        heading = label('What would you like to explore?', 'title')
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.addWidget(heading)
        subheading = label('Ask a question, or bring a document.', 'muted')
        subheading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.addWidget(subheading)
        self.messages_layout.insertWidget(0, self.empty)

        bottom = QWidget()
        bottom.setMaximumWidth(760)
        bottom.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        area = QVBoxLayout(bottom)
        area.setContentsMargins(0, 0, 0, 0)
        area.setSpacing(10)
        self.notice = label('', 'notice')
        self.notice.hide()
        area.addWidget(self.notice)
        self.scope = label('', 'muted')
        area.addWidget(self.scope)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        area.addWidget(self.progress)
        composer = QFrame()
        composer.setObjectName('composer')
        compose = QVBoxLayout(composer)
        compose.setContentsMargins(14, 10, 14, 10)
        self.question = Composer()
        self.question.setPlaceholderText('Message SecureRAG')
        self.question.setFixedHeight(60)
        self.question.send.connect(self.ask)
        compose.addWidget(self.question)
        tools = QHBoxLayout()
        self.attach_button = self.button('+', self.upload)
        self.attach_button.setToolTip('Attach a document')
        self.attach_button.setAccessibleName('Attach a document')
        tools.addWidget(self.attach_button)
        tools.addWidget(label('Local processing', 'muted'))
        tools.addStretch()
        self.send_button = self.button('Send', self.ask, True)
        tools.addWidget(self.send_button)
        compose.addLayout(tools)
        area.addWidget(composer)
        self.status = label('Loading local models…', 'muted')
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        area.addWidget(self.status)
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        bottom_row.addWidget(bottom, 1)
        bottom_row.addStretch()
        main.addLayout(bottom_row)
        root.addLayout(main, 1)
        self.selection_changed()

    def show_settings(self):
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.animate(self.settings_dialog)

    def toggle_sidebar(self):
        target = 0 if self.sidebar.maximumWidth() > 120 else 248
        if hasattr(self, 'sidebar_animation'):
            self.sidebar_animation.stop()
        if self.motion.isChecked():
            self.sidebar.setMaximumWidth(target)
            return
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b'maximumWidth', self)
        self.sidebar_animation.setStartValue(self.sidebar.width())
        self.sidebar_animation.setEndValue(target)
        self.sidebar_animation.setDuration(260)
        self.sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.sidebar_animation.start()

    def selected_source(self):
        item = self.documents.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def selection_changed(self, *args):
        source = self.selected_source()
        self.summary_button.setVisible(bool(source))
        self.remove_button.setVisible(bool(source))
        self.scope.setVisible(self.mode.currentData() == 'documents')
        if self.mode.currentData() == 'documents':
            self.scope.setText('Using: ' + (Path(source).name if source else 'All indexed documents · select one for an overview'))
        else:
            self.scope.setText('')

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.new_button, self.connect_button, self.use_model_button,
                       self.upload_button, self.remove_button, self.summary_button,
                       self.send_button, self.mode, self.documents, self.model, self.events_button, self.attach_button):
            widget.setEnabled(not busy)
        self.progress.setVisible(busy)

    def submit(self, operation, *args):
        if self.busy:
            return
        self.set_busy(True)
        self.status.setText({'ask': 'Checking the question, gathering context and generating…',
                             'ingest': 'Reading and screening the document…',
                             'available_models': 'Connecting to local Ollama…'}.get(operation, 'Updating workspace…'))
        def work():
            backend = self.backend_future.result()
            result = getattr(backend, operation)(*args)
            return result, backend.snapshot()
        future = self.pool.submit(work)
        def finish(done):
            try:
                result, snapshot = done.result()
                self.signals.completed.emit(operation, result, snapshot)
            except Exception as exc:
                self.signals.failed.emit(str(exc))
        future.add_done_callback(finish)

    def animate(self, widget):
        if self.motion.isChecked():
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b'opacity', widget)
        animation.setDuration(240)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        widget._fade = animation

    def notify(self, text, warning=False):
        self.notice.setText(text)
        self.notice.setProperty('warning', warning)
        self.notice.style().unpolish(self.notice)
        self.notice.style().polish(self.notice)
        self.notice.show()
        self.settings_status.setText(text)
        self.animate(self.notice)

    def add_message(self, sender, text, sources=None):
        self.empty.hide()
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        user = sender == 'You'
        card.setObjectName('userMessage' if user else 'assistantMessage')
        box = QVBoxLayout(card)
        box.setContentsMargins(18 if user else 0, 14, 18 if user else 0, 12)
        box.setSpacing(12)
        if not user:
            box.addWidget(label('SecureRAG', 'brand'))
        body = label(text)
        body.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(body)
        for source in sources or []:
            box.addWidget(label(f"{Path(source['source']).name} · excerpt {source['chunk_index'] + 1}", 'muted'))
        if not user:
            copy = self.button('Copy', lambda: QApplication.clipboard().setText(text))
            copy.setMaximumWidth(65)
            box.addWidget(copy)
        if user:
            line.addStretch(1)
            line.addWidget(card, 4)
        else:
            line.addWidget(card)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self.animate(row)
        QTimer.singleShot(40, self.scroll_to_end)

    def scroll_to_end(self):
        bar = self.scroll.verticalScrollBar()
        if self.motion.isChecked():
            bar.setValue(bar.maximum())
            return
        if hasattr(self, 'scroll_animation'):
            self.scroll_animation.stop()
        self.scroll_animation = QPropertyAnimation(bar, b'value', self)
        self.scroll_animation.setStartValue(bar.value())
        self.scroll_animation.setEndValue(bar.maximum())
        self.scroll_animation.setDuration(220)
        self.scroll_animation.start()

    def clear_chat(self):
        for index in reversed(range(self.messages_layout.count() - 1)):
            widget = self.messages_layout.itemAt(index).widget()
            if widget is not self.empty:
                self.messages_layout.takeAt(index).widget().deleteLater()
        self.empty.show()

    def ask(self, overview=False):
        if self.busy:
            return
        text = self.question.toPlainText().strip()
        if not text:
            return
        self.question.clear()
        self.add_message('You', text)
        self.submit('ask', text, self.mode.currentData(), self.selected_source(), bool(overview))

    def summarize(self):
        if not self.selected_source():
            self.notify('Select a document in the library first.', True)
            return
        self.mode.setCurrentIndex(1)
        self.question.setPlainText('Summarize this document and explain its main points.')
        self.ask(True)

    def upload(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Add document', '', 'Documents (*.pdf *.docx *.txt *.md)')
        if filename:
            self.submit('ingest', filename)

    def remove_selected(self):
        source = self.selected_source()
        if source and QMessageBox.question(self, 'Remove document',
                'Remove this document from the index? The original file is kept.') == QMessageBox.StandardButton.Yes:
            self.submit('remove_document', source)

    def select_model(self):
        if self.model.currentText():
            self.submit('set_model', self.model.currentText())

    def show_events(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Security activity · latest decisions')
        dialog.resize(760, 500)
        layout = QVBoxLayout(dialog)
        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText('\n\n'.join(
            f"{row.get('time', '')}\n{row.get('event', '').replace('_', ' ').title()} · "
            f"{row.get('decision', row.get('status', ''))}\n{row.get('reason', row.get('source', ''))}"
            for row in reversed(self.last_events)))
        layout.addWidget(viewer)
        dialog.exec()

    def refresh_snapshot(self, snapshot, selected=None):
        selected = selected or self.selected_source()
        self.last_events = snapshot['events']
        self.active_model = snapshot['model']
        if self.model.findText(self.active_model) < 0:
            self.model.addItem(self.active_model)
        self.model.setCurrentText(self.active_model)
        self.documents.clear()
        for row in snapshot['documents']:
            good, bad = row['indexed_chunks'], row['quarantined_chunks']
            state = 'Blocked' if not good else ('Partially approved' if bad else 'Approved')
            item = QListWidgetItem(f"{Path(row['source']).name}\n{state}")
            item.setData(Qt.ItemDataRole.UserRole, row['source'])
            item.setToolTip(f"{row['source']}\n{good} approved excerpts; {bad} quarantined excerpts")
            item.setForeground(QColor('#8d5140' if bad else '#454545'))
            self.documents.addItem(item)
            if row['source'] == selected:
                self.documents.setCurrentItem(item)
        self.selection_changed()

    def on_completed(self, operation, result, snapshot):
        self.refresh_snapshot(snapshot, result['source'] if operation == 'ingest' else None)
        self.set_busy(False)
        self.status.setText(f"Ready · {self.active_model} · local processing")
        if operation == 'available_models':
            self.model.clear()
            self.model.addItems(result)
            if self.active_model in result:
                self.model.setCurrentText(self.active_model)
            self.notify(f'Ollama connected · {len(result)} installed models.' if result else 'Ollama is running. Install a model before chatting.', not result)
        elif operation == 'set_model':
            self.notify(f'Connected to {result}.')
        elif operation == 'ingest':
            good, bad = result['indexed_chunks'], result['quarantined_chunks']
            if not good:
                self.notify(f"Blocked: {Path(result['source']).name}. All {bad} excerpts were quarantined. Nothing from this file can be retrieved.", True)
            else:
                self.mode.setCurrentIndex(1)
                self.notify(f"{Path(result['source']).name}: {good} approved excerpts are ready. {bad} quarantined excerpts were excluded.", bool(bad))
        elif operation == 'remove_document':
            self.notify('Document removed from the index. Original file kept.')
        elif operation == 'ask':
            self.add_message('SecureRAG', result['answer'], result.get('sources'))
            if result['status'] != 'ANSWERED':
                self.notify(result['answer'], True)
            else:
                self.notice.hide()

    def on_failed(self, message):
        self.set_busy(False)
        self.status.setText('Operation failed · details above')
        self.notify(message, True)

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if self.busy:
            return
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if len(files) != 1:
            self.notify('Please drop one document at a time.', True)
        else:
            self.submit('ingest', files[0])

    def closeEvent(self, event):
        if self.busy:
            self.notify('Please wait for the current operation to finish before closing.', True)
            event.ignore()
            return
        self.pool.shutdown(wait=False, cancel_futures=True)
        event.accept()


def run_gui():
    app = QApplication([])
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    return app.exec()
