"""Local durable outbox and idempotent SQL delivery. No connection values are logged."""
from __future__ import annotations
import json, sqlite3, threading, time
from pathlib import Path
from contextlib import contextmanager
from .live_rules import utc_now

class Outbox:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS outbox (key TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL DEFAULT 0)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.execute('PRAGMA busy_timeout=10000')
        try:
            with db:yield db
        finally:db.close()
    def put(self,kind,key,payload):
        with self.connect() as db:
            db.execute('INSERT INTO outbox(key,kind,payload) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,kind=excluded.kind,revision=outbox.revision+1',
                       (key,kind,json.dumps(payload,ensure_ascii=False)))
    def due(self):
        with self.connect() as db:
            return db.execute('SELECT key,kind,payload,revision,attempts FROM outbox WHERE retry_at<=? ORDER BY rowid LIMIT 50',(time.time(),)).fetchall()
    def ack(self,key,revision):
        with self.connect() as db:db.execute('DELETE FROM outbox WHERE key=? AND revision=?',(key,revision))
    def retry(self,key,revision,attempts):
        with self.connect() as db:db.execute('UPDATE outbox SET attempts=?,retry_at=? WHERE key=? AND revision=?',(attempts+1,time.time()+min(30,2**min(attempts,5)),key,revision))
    def interrupt_open_events(self):
        with self.connect() as db:
            for key,raw in db.execute("SELECT key,payload FROM outbox WHERE kind='event'").fetchall():
                event=json.loads(raw)
                if event.get('status')=='open':
                    event.update(status='interrupted',close_reason='service_restarted',closed_at=utc_now())
                    db.execute('UPDATE outbox SET payload=?,revision=revision+1 WHERE key=?',(json.dumps(event),key))
    def count(self):
        with self.connect() as db:return db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]

class EventStore:
    def __init__(self,url,create_tables=True,recover_cameras=None):
        from sqlalchemy import create_engine,MetaData,Table,Column,String,JSON,Float
        from sqlalchemy.engine import make_url
        self.url=url;parsed=make_url(url);dialect=parsed.get_backend_name()
        if dialect not in {'sqlite','postgresql','mysql'}:raise ValueError('Unsupported database dialect')
        args={'timeout':5} if dialect=='sqlite' else {'connect_timeout':5}
        if dialect=='mysql':args.update(read_timeout=5,write_timeout=5)
        if dialect=='sqlite':args['check_same_thread']=False
        self.engine=create_engine(url,pool_pre_ping=True,connect_args=args,hide_parameters=True)
        self.recover_cameras=recover_cameras or [];self.meta=MetaData();self.create_tables=create_tables;self.initialized=False;self.lock=threading.RLock()
        self.events=Table('sorting_events',self.meta,Column('event_id',String(64),primary_key=True),
                          Column('site_id',String(64),nullable=False),Column('camera_id',String(64),nullable=False,index=True),
                          Column('event_type',String(40),nullable=False,index=True),Column('status',String(24),nullable=False),
                          Column('start_at',String(40),nullable=False,index=True),Column('end_at',String(40)),
                          Column('duration_seconds',Float),Column('review_status',String(24)),Column('snapshot_path',String(1024)),
                          Column('clip_path',String(1024)),Column('payload',JSON,nullable=False))
        self.cameras=Table('sorting_camera_status',self.meta,Column('camera_id',String(64),primary_key=True),
                           Column('site_id',String(64),primary_key=True),Column('state',String(32),nullable=False),
                           Column('heartbeat_at',String(40),nullable=False),Column('payload',JSON,nullable=False))
    def initialize(self):
        with self.lock:
            if not self.initialized:
                if self.create_tables:self.meta.create_all(self.engine)
                else:
                    with self.engine.connect() as conn:conn.exec_driver_sql('SELECT 1')
                if self.recover_cameras:
                    from sqlalchemy import select, update
                    with self.engine.begin() as conn:
                        for site,camera in self.recover_cameras:
                            query=select(self.events.c.payload).where((self.events.c.site_id==site)&(self.events.c.camera_id==camera)&(self.events.c.status=='open'))
                            for row in conn.execute(query).all():
                                payload=dict(row[0],status='interrupted',close_reason='service_restarted',closed_at=utc_now())
                                conn.execute(update(self.events).where(self.events.c.event_id==payload['event_id']).values(status='interrupted',payload=payload))
                self.initialized=True
    def deliver(self,kind,payload):
        from sqlalchemy import insert,update
        self.initialize()
        if kind=='event':
            table=self.events;key='event_id'
            values={k:payload.get(k) for k in ['event_id','site_id','camera_id','event_type','status','start_at','end_at','duration_seconds','review_status','snapshot_path','clip_path']}
        else:
            table=self.cameras;key='camera_id'
            values={k:payload.get(k) for k in ['camera_id','site_id','state','heartbeat_at']}
        values['payload']=payload
        # A single delivery thread owns writes. Retried commits update the same PK.
        with self.lock,self.engine.begin() as conn:
            condition=table.c[key]==values[key]
            if kind!='event':condition=condition & (table.c.site_id==values['site_id'])
            existing=conn.execute(table.select().where(condition)).first()
            if existing:conn.execute(update(table).where(condition).values(**values))
            else:
                from sqlalchemy.exc import IntegrityError
                try:
                    with conn.begin_nested():conn.execute(insert(table).values(**values))
                except IntegrityError:conn.execute(update(table).where(condition).values(**values))
    def list_events(self,camera_id=None,limit=50,event_id=None,site_id=None):
        from sqlalchemy import select
        self.initialize();q=select(self.events.c.payload)
        if camera_id:q=q.where(self.events.c.camera_id==camera_id)
        if event_id:q=q.where(self.events.c.event_id==event_id)
        if site_id:q=q.where(self.events.c.site_id==site_id)
        q=q.order_by(self.events.c.start_at.desc()).limit(min(200,max(1,limit)))
        with self.engine.connect() as conn:return [row[0] for row in conn.execute(q)]

class Delivery:
    def __init__(self,outbox,store):
        self.outbox=outbox;self.store=store;self.stop_event=threading.Event();self.error=None;self.last_success=None
        self.thread=threading.Thread(target=self.run,name='database-delivery',daemon=True)
    def start(self):self.thread.start()
    def run_once(self):
        for key,kind,raw,revision,attempts in self.outbox.due():
            if self.stop_event.is_set():break
            try:
                self.store.deliver(kind,json.loads(raw));self.outbox.ack(key,revision)
                self.last_success=utc_now();self.error=None
            except Exception as exc:
                self.error=type(exc).__name__;self.outbox.retry(key,revision,attempts)
                break
    def run(self):
        while not self.stop_event.is_set():
            try:self.run_once()
            except Exception as exc:self.error=type(exc).__name__
            self.stop_event.wait(.2)
    def stop(self):
        self.stop_event.set();self.thread.join(timeout=8)
    def status(self):
        return dict(pending=self.outbox.count(),error_code=self.error,last_success=self.last_success,writer_alive=self.thread.is_alive())
