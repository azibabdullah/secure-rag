import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# Offscreen render tests use software rendering; production keeps GPU acceleration.
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
from time import monotonic, sleep
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase
from src.gui.web_app import DashboardWindow
from unittest.mock import Mock

class Backend:
    def __init__(self):
        self.calls=[]
        self.uploads=[]
        self.settings={'dark': True, 'motion': None, 'screen_documents_on_upload': True}
        self.conversations = Mock()
        self.conversations.create.return_value = {'id': 'test-session'}
    def preferences(self, changes):
        self.settings.update(changes)
        return self.settings
    def ingest_many(self, filenames):
        self.uploads = filenames
        return {'files': [{'filename': filenames[0], 'result': {'source': 'DES.pdf', 'indexed_chunks': 3, 'quarantined_chunks': 0}},
                          {'filename': filenames[1], 'error': 'Unreadable test PDF'}], 'cancelled': False, 'remaining': []}
    def document_decision(self, source):
        return {'document': {'source': source, 'indexed_chunks': 3, 'quarantined_chunks': 0},
                'threshold': .5, 'retrieval_threshold': .5, 'explanation': 'A score is not a reasoning trace.',
                'rows': [{'chunk_index': 0, 'decision': 'SAFE', 'score': .01, 'text': '<script>blockedHTML()</script>',
                          'reason': 'Score 0.010000 is below threshold 0.500.'}]}
    def snapshot(self):
        return {'model':'llama3:8b', 'preferences': self.settings,'documents':[
            {'source':'DES.pdf','indexed_chunks':3,'quarantined_chunks':0},
            {'source':'poisoned.txt','indexed_chunks':0,'quarantined_chunks':1}],
            'events':[{'time':'2026-10-21T10:00:00Z','event':'query','decision':'SAFE','score':.02},
                      {'time':'2026-10-21T10:01:00Z','event':'ingestion_chunk','decision':'QUARANTINED','score':.97}]}
    def ask(self, question, mode, source, overview, **kwargs):
        self.calls.append((question,mode,source,overview))
        return {'status':'ANSWERED','answer':'A supported answer. <script>bad()</script>', 'sources':[{'source':source,'chunk_index':0}]}
    def available_models(self): return ['llama3:8b']

def pump(app, seconds=.1):
    end=monotonic()+seconds
    while monotonic()<end:
        app.processEvents();sleep(.01)

def js(app,window,code):
    result=[]
    window.page.runJavaScript(code, result.append)
    deadline=monotonic()+5
    while not result and monotonic()<deadline: pump(app)
    assert result, 'JavaScript callback timed out'
    return result[0]

def test_web_bridge_and_render(monkeypatch):
    app=QApplication.instance() or QApplication(['SecureRAG'])
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/'segoeui.ttf'))
    backend=Backend()
    window=DashboardWindow(lambda:backend)
    window.show()
    deadline=monotonic()+15
    while monotonic()<deadline:
        pump(app,.2)
        if js(app,window,"document.querySelectorAll('.doc').length") == 2: break
    assert js(app,window,"document.querySelectorAll('.doc').length") == 2
    js(app,window,"document.querySelector('.doc').click()")
    pump(app)
    js(app,window,"Array.from(document.querySelectorAll('.doc-actions button')).find(b=>b.textContent.includes('Explain')).click()")
    pump(app, .5)
    assert '0.500' in js(app,window,"document.querySelector('.decision-panel').textContent")
    assert js(app,window,"document.querySelector('.decision-panel script') === null")
    js(app,window,"Array.from(document.querySelectorAll('.doc-actions button')).find(b=>b.textContent.includes('Summarize')).click()")
    deadline=monotonic()+5
    while not backend.calls and monotonic()<deadline: pump(app)
    assert backend.calls[0][1:] == ('documents','DES.pdf',True)
    pump(app,1)
    assert js(app,window,"document.querySelector('.assistant p').textContent") == 'A supported answer. <script>bad()</script>'
    assert js(app,window,"document.querySelector('.assistant script') === null")
    monkeypatch.setattr('src.gui.web_app.QFileDialog.getOpenFileNames', lambda *args: (['a.pdf','b.pdf'], ''))
    js(app,window,"document.querySelector('[aria-label=\"Add document\"]').click()")
    pump(app,.5)
    assert backend.uploads == ['a.pdf', 'b.pdf']
    assert 'Unreadable test PDF' in js(app,window,"document.querySelector('.batch-results').textContent")
    js(app,window,"document.querySelector('[data-nav=\"settings\"]').click()")
    pump(app,.3)
    js(app,window,"Array.from(document.querySelectorAll('.toggle-row')).find(e=>e.textContent.includes('Screen documents')).querySelector('input').click()")
    pump(app,.5)
    assert backend.settings['screen_documents_on_upload'] is False
    assert 'Upload screening OFF' in js(app,window,"document.body.textContent")
    pump(app,2)
    window.view.repaint()
    window.view.grab().save('tests/web_dashboard_dark.png')
    js(app,window,"document.querySelector('[aria-label=\"Switch to light mode\"]').click()")
    pump(app,.3)
    assert js(app,window,"document.documentElement.dataset.theme") == 'light'
    assert js(app,window,"getComputedStyle(document.body).backgroundColor") == 'rgb(242, 243, 246)'
    pump(app,2)
    window.view.repaint()
    window.view.grab().save('tests/web_dashboard_light.png')
    window.close()
