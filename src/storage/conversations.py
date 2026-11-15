from datetime import datetime, timezone
from uuid import uuid4


class Conversations:
    def __init__(self, vault):
        self.vault = vault

    def create(self):
        session = {'id': uuid4().hex, 'title': 'New conversation', 'turns': [], 'updated': datetime.now(timezone.utc).isoformat()}
        self.vault.put('session', session['id'], session)
        return session

    def get(self, ident):
        session = self.vault.get('session', ident)
        if session is None:
            raise ValueError('Conversation no longer exists.')
        return session

    def list(self):
        return [{k: s[k] for k in ('id', 'title', 'updated')} for s in sorted(self.vault.all('session'), key=lambda s: s['updated'], reverse=True)]

    def append(self, ident, question, result, mode, source):
        session = self.get(ident)
        session['turns'].append({'question': question, 'result': result, 'mode': mode, 'source': source})
        session['turns'] = session['turns'][-100:]
        if session['title'] == 'New conversation':
            session['title'] = question[:60]
        session['updated'] = datetime.now(timezone.utc).isoformat()
        self.vault.put('session', ident, session)

    def history(self, ident, mode, source):
        if not ident:
            return []
        # Only contiguous successful turns from this same source/mode are eligible.
        turns = []
        for turn in reversed(self.get(ident)['turns']):
            if turn['mode'] != mode or turn['source'] != source:
                break
            if turn['result']['status'] == 'ANSWERED':
                turns.insert(0, turn)
            if len(turns) == 3:
                break
        return turns
