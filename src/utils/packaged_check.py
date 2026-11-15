"""Installed-build diagnostic using an isolated profile, CPU inference and WebEngine."""
import json
import os
from pathlib import Path
import tempfile
import traceback


def run(report_path):
    report = {'passed': False}
    try:
        with tempfile.TemporaryDirectory(prefix='securerag-packaged-') as directory:
            os.environ['SECURERAG_DATA_DIR'] = str(Path(directory) / 'profile')
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            from src.rag.pipeline import SecureRAG
            backend = SecureRAG()
            report['device'] = str(backend.classifier.device)
            report['classifier'] = backend.classifier.classify('What is this document about?')
            report['document_guard'] = backend.doc_classifier.classify('The laboratory opens at 09:30 each weekday.')
            document = Path(directory) / 'sample.txt'
            document.write_text('The laboratory opens at 09:30 each weekday.', encoding='utf-8')
            report['ingestion'] = backend.ingest(str(document))
            report['retrieved'] = len(backend.store.retrieve('When does the laboratory open?'))
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            from src.gui.web_app import DashboardWindow
            app = QApplication.instance() or QApplication(['SecureRAG'])
            window = DashboardWindow(lambda: backend)
            window.show()
            def inspect():
                window.page.runJavaScript("document.querySelectorAll('.shell').length", lambda count: report.update(frontend_loaded=count == 1))
            QTimer.singleShot(5000, inspect)
            QTimer.singleShot(6500, app.quit)
            app.exec()
            window.close()
            backend.store.close()
            report['passed'] = (report['device'] == 'cpu' and report['classifier']['label'] == 'SAFE' and report['document_guard']['label'] == 'SAFE'
                                and report['ingestion']['indexed_chunks'] > 0 and report['retrieved'] > 0 and report.get('frontend_loaded', False))
    except Exception:
        report['error'] = traceback.format_exc()
    Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1
