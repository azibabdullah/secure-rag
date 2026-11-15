import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from time import monotonic, sleep
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from src.gui.app import MainWindow


class Backend:
    def snapshot(self):
        return {'model': 'llama3:8b', 'events': [], 'documents': [
            {'source': 'DES.pdf', 'indexed_chunks': 1, 'quarantined_chunks': 0},
            {'source': 'poisoned_policy_note.txt', 'indexed_chunks': 0, 'quarantined_chunks': 1}]}
    def ask(self, question, mode, source, overview):
        assert source == 'DES.pdf'
        return {'status': 'ANSWERED', 'answer': 'DES is a block cipher. This answer is based on the selected document.',
                'sources': [{'source': source, 'chunk_index': 0}]}


def wait(app, window):
    deadline = monotonic() + 3
    while window.busy and monotonic() < deadline:
        app.processEvents()
        sleep(.01)
    assert not window.busy


def test_selection_summary_and_render():
    app = QApplication.instance() or QApplication(['SecureRAG'])
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / 'segoeui.ttf'))
    app.setStyle('Fusion')
    window = MainWindow(Backend)
    window.show()
    wait(app, window)
    window.documents.setCurrentRow(0)
    QTest.mouseClick(window.summary_button, Qt.MouseButton.LeftButton)
    wait(app, window)
    QTest.qWait(400)
    assert window.mode.currentData() == 'documents'
    assert 'DES.pdf' in window.scope.text()
    assert window.last_events == []
    window.notify('Blocked: poisoned_policy_note.txt. All excerpts quarantined. Nothing from this file can be retrieved.', True)
    QTest.qWait(350)
    output = Path('tests/ui_preview.png')
    assert window.grab().save(str(output))
    window.close()



def test_sidebar_settings_and_empty_state():
    app = QApplication.instance() or QApplication(['SecureRAG'])
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / 'segoeui.ttf'))
    window = MainWindow(Backend)
    window.show()
    wait(app, window)
    assert window.empty.isVisible()
    assert not window.settings_dialog.isVisible()
    assert not window.summary_button.isVisible()
    window.grab().save('tests/ui_empty_preview.png')
    QTest.mouseClick(window.sidebar_button, Qt.MouseButton.LeftButton)
    QTest.qWait(320)
    assert window.sidebar.width() == 0
    QTest.mouseClick(window.sidebar_button, Qt.MouseButton.LeftButton)
    QTest.qWait(320)
    assert window.sidebar.width() == 248
    window.show_settings()
    QTest.qWait(300)
    assert window.model.isVisible()
    window.motion.setChecked(True)
    window.settings_dialog.accept()
    window.toggle_sidebar()
    assert window.sidebar.maximumWidth() == 0
    window.toggle_sidebar()
    window.resize(850, 640)
    app.processEvents()
    assert window.question.width() > 250
    window.clear_chat()
    assert window.empty.isVisible()
    window.close()
