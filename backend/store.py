"""Small document-store adapter: SQLite for local practice, MongoDB for deployment."""
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def connection(path):
    c = sqlite3.connect(path)
    try:
        with c: yield c
    finally: c.close()

class SQLiteStore:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with connection(path) as c:
            c.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))')
    def insert(self, kind, doc):
        try:
            with connection(self.path) as c:
                c.execute('INSERT INTO records VALUES (?,?,?)', (kind, doc['id'], json.dumps(doc)))
            return True
        except sqlite3.IntegrityError:
            return False
    def get(self, kind, id):
        with connection(self.path) as c:
            row = c.execute('SELECT body FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()
        return json.loads(row[0]) if row else None
    def all(self, kind):
        with connection(self.path) as c:
            return [json.loads(r[0]) for r in c.execute('SELECT body FROM records WHERE kind=?',(kind,))]
    def update(self, kind, id, expected, changes):
        with connection(self.path) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT body FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()
            if not row: return None
            doc = json.loads(row[0])
            if any(doc.get(k)!=v for k,v in expected.items()): return None
            doc.update(changes)
            c.execute('UPDATE records SET body=? WHERE kind=? AND id=?',(json.dumps(doc),kind,id))
            return doc
    def ping(self):
        with connection(self.path) as c: c.execute('SELECT 1')

class MongoStore:
    def __init__(self, uri, database):
        from pymongo import MongoClient
        self.client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        self.db = self.client[database]
    def insert(self, kind, doc):
        from pymongo.errors import DuplicateKeyError
        try: self.db[kind].insert_one({**doc, '_id':doc['id']}); return True
        except DuplicateKeyError: return False
    def get(self, kind, id): return self.db[kind].find_one({'_id':id},{'_id':0})
    def all(self, kind): return list(self.db[kind].find({}, {'_id':0}))
    def update(self, kind, id, expected, changes):
        from pymongo import ReturnDocument
        return self.db[kind].find_one_and_update({'_id':id,**expected},{'$set':changes},projection={'_id':0},return_document=ReturnDocument.AFTER)
    def ping(self): self.client.admin.command('ping')
