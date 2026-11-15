"""Local web UI. Only this bundled page receives the bounded Python bridge."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, QLockFile, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from src.utils.app_paths import assets_dir, user_data_dir
from src.utils.operations import Operation, current_operation


class LocalPage(QWebEnginePage):
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry.resolve()

    def acceptNavigationRequest(self, url, kind, main_frame):
        return url.isLocalFile() and Path(url.toLocalFile()).resolve() == self.entry


class DesktopBridge(QObject):
    response = pyqtSignal(str)
    completed = pyqtSignal(str, object, str)
    progress = pyqtSignal(str)

    def __init__(self, parent=None, backend_factory=None):
        super().__init__(parent)
        self.busy = False
        self.operation = None
        self.pool = ThreadPoolExecutor(max_workers=1)
        if backend_factory is None:
            def backend_factory():
                from src.rag.pipeline import SecureRAG
                return SecureRAG()
        self.backend = self.pool.submit(backend_factory)
        self.completed.connect(self.finish)

    @pyqtSlot(str)
    def request(self, raw):
        ident = ''
        claimed = False
        try:
            message = json.loads(raw)
            ident = str(message['id'])
            operation, args = message['operation'], message.get('args', {})
            if operation == 'cancel':
                if self.operation:
                    self.operation.cancelled.set()
                self.response.emit(json.dumps({'id': ident, 'result': {'result': True}}))
                return
            if operation == 'copy':
                QApplication.clipboard().setText(str(args['text']))
                self.response.emit(json.dumps({'id': ident, 'result': {'result': True}}))
                return
            if operation not in {'snapshot', 'ask', 'upload', 'remove', 'models', 'model',
                                 'preferences', 'session_new', 'session_get', 'session_delete', 'preview', 'migrate', 'decision'}:
                raise ValueError('Unsupported desktop operation')
            if self.busy:
                raise RuntimeError('Wait for the current operation to finish')
            self.busy = True
            claimed = True
            self.operation = Operation(notify=lambda phase: self.progress.emit(json.dumps({'phase': phase})))
            if operation == 'upload':
                filenames, _ = QFileDialog.getOpenFileNames(self.parent(), 'Add documents', '',
                    'Documents (*.pdf *.docx *.txt *.md)')
                if not filenames:
                    self.busy = False
                    self.response.emit(json.dumps({'id': ident, 'result': {'result': None}}))
                    return
                args = {'filenames': filenames}
            elif operation in {'remove', 'session_delete'}:
                if QMessageBox.question(self.parent(), 'Remove document',
                        'Delete this saved conversation?' if operation == 'session_delete' else
                        'Remove this document from the index? The original file is kept.') != QMessageBox.StandardButton.Yes:
                    self.busy = False
                    self.response.emit(json.dumps({'id': ident, 'result': {'result': None}}))
                    return

            def dispatch():
                backend = self.backend.result()
                self.operation.check()
                if operation == 'ask':
                    result = backend.ask(str(args['question']), str(args.get('mode', 'chat')),
                                         args.get('source'), bool(args.get('overview', False)),
                                         **({'session_id': args['session_id']} if args.get('session_id') else {}),
                                         report=bool(args.get('report', False)))
                elif operation == 'upload':
                    result = backend.ingest_many(args['filenames'])
                elif operation == 'decision':
                    result = backend.document_decision(args['source'])
                elif operation == 'remove':
                    result = backend.remove_document(args['source'])
                elif operation == 'models':
                    result = backend.available_models()
                elif operation == 'model':
                    result = backend.set_model(args['name'])
                elif operation == 'preferences':
                    result = backend.preferences(args)
                elif operation == 'session_new':
                    result = backend.conversations.create()
                elif operation == 'session_get':
                    result = backend.conversations.get(args['id'])
                elif operation == 'session_delete':
                    backend.store.vault.delete('session', args['id'])
                    result = True
                elif operation == 'preview':
                    result = backend.store.preview(args['source'])
                elif operation == 'migrate':
                    result = backend.store.import_legacy()
                else:
                    result = None
                return {'result': result, 'snapshot': backend.snapshot()}

            def work():
                token = current_operation.set(self.operation)
                try:
                    return dispatch()
                finally:
                    current_operation.reset(token)

            def done(future):
                try:
                    self.completed.emit(ident, future.result(), '')
                except Exception as exc:
                    self.completed.emit(ident, None, str(exc))
            self.pool.submit(work).add_done_callback(done)
        except Exception as exc:
            # Do not release a different job's busy flag when a concurrent request is rejected.
            if claimed:
                self.busy = False
                self.operation = None
            self.response.emit(json.dumps({'id': ident, 'error': str(exc)}))

    @pyqtSlot(str, object, str)
    def finish(self, ident, result, error):
        self.busy = False
        self.operation = None
        self.response.emit(json.dumps({'id': ident, 'result': result, 'error': error}))


class DashboardWindow(QMainWindow):
    def __init__(self, backend_factory=None):
        super().__init__()
        self.setWindowTitle('SecureRAG')
        self.resize(1440, 940)
        self.setMinimumSize(850, 650)
        entry = assets_dir() / 'frontend' / 'dist' / 'index.html'
        if not entry.exists():
            raise FileNotFoundError('Build the frontend first: npm --prefix frontend run build')
        self.view = QWebEngineView(self)
        self.page = LocalPage(entry, self.view)
        self.view.setPage(self.page)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        self.channel = QWebChannel(self.page)
        self.bridge = DesktopBridge(self, backend_factory)
        self.channel.registerObject('desktop', self.bridge)
        self.page.setWebChannel(self.channel)
        self.setCentralWidget(self.view)
        self.view.load(QUrl.fromLocalFile(str(entry)))

    def closeEvent(self, event):
        if self.bridge.busy or not self.bridge.backend.done():
            QMessageBox.information(self, 'Operation in progress', 'Wait for the local operation to finish before closing.')
            event.ignore()
            return
        self.bridge.pool.shutdown(wait=False, cancel_futures=True)
        event.accept()


def run_dashboard():
    if sys.platform == 'win32':
        # Own taskbar identity, so Windows shows the SecureRAG icon (not Python's) when run from source.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('SecureRAG.Desktop')
        except (AttributeError, OSError):
            pass
    app = QApplication(['SecureRAG'])
    icon = assets_dir() / 'assets' / 'securerag.ico'
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    lock = QLockFile(str(user_data_dir() / 'desktop.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, 'SecureRAG is already open', 'Use the existing SecureRAG window.')
        return 1
    window = DashboardWindow()
    window.show()
    return app.exec()
