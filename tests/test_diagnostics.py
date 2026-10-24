import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sorting_vision.configure import connection_url,write_environment
from sorting_vision.runtime_env import load_runtime_env
from sorting_vision.diagnostics import database_probe,main
from sorting_vision.event_store import EventStore


class FieldDiagnosticsTests(unittest.TestCase):
    def test_secret_url_and_literal_environment_round_trip(self):
        password='demo@!$with${OTHER}#and:slash/'
        url=connection_url('mysql+pymysql','database.invalid',3306,'user',password,'sorting')
        from sqlalchemy.engine import make_url
        self.assertEqual(password,make_url(url).password)
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'OTHER':'must-not-expand'},clear=True):
            path=Path(directory)/'.env'
            values={'SORTING_DATABASE_URL':url,'LITERAL':'${OTHER}', 'WIN_PATH':r'C:\sorting vision\runs', 'QUOTED':"a'b"}
            write_environment(path,values);load_runtime_env(path)
            for key,value in values.items():self.assertEqual(value,os.environ[key])
            with self.assertRaises(FileExistsError):write_environment(path,{'LITERAL':'changed'})
            load_runtime_env(path);self.assertEqual('${OTHER}',os.environ['LITERAL'])

    def test_read_only_database_probe_does_not_create_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            url='sqlite:///'+str(Path(directory)/'probe.db')
            result=database_probe(url)
            self.assertFalse(result['passed']);self.assertFalse(result['ddl_executed'])
            from sqlalchemy import create_engine,inspect
            engine=create_engine(url)
            self.assertEqual([],inspect(engine).get_table_names());engine.dispose()

    def test_crud_probe_rolls_back_both_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            url='sqlite:///'+str(Path(directory)/'probe.db')
            store=EventStore(url);store.initialize()
            self.assertTrue(database_probe(url)['passed'])
            result=database_probe(url,write_test=True)
            self.assertTrue(result['passed']);self.assertEqual('passed_and_rolled_back',result['crud_test'])
            self.assertFalse(result['durable_commit_verified'])
            with store.engine.connect() as conn:
                self.assertEqual([],conn.execute(store.events.select()).all())
                self.assertEqual([],conn.execute(store.cameras.select()).all())
            store.engine.dispose()

    def test_cli_failure_never_prints_database_url(self):
        secret='mysql+pymysql://user:example-secret@unreachable.invalid/db'
        with patch.dict(os.environ,{'SORTING_DATABASE_URL':secret}),patch('sys.argv',['diagnostics','database']),patch('sorting_vision.diagnostics.database_probe',side_effect=RuntimeError(secret)):
            output=io.StringIO()
            with contextlib.redirect_stdout(output),self.assertRaises(SystemExit) as error:main()
            self.assertEqual(2,error.exception.code);self.assertNotIn('example-secret',output.getvalue())
            self.assertFalse(json.loads(output.getvalue())['passed'])

    def test_write_probe_failure_rolls_back_and_preserves_existing_data(self):
        from sqlalchemy.engine import Connection
        from sqlalchemy.sql.dml import Update
        with tempfile.TemporaryDirectory() as directory:
            url='sqlite:///'+str(Path(directory)/'probe.db')
            store=EventStore(url);store.initialize()
            original=dict(event_id='existing',site_id='actual-site',camera_id='actual-camera',event_type='chute_stall',status='closed',start_at='2026-10-24T00:00:00Z',duration_seconds=3.)
            store.deliver('event',original)
            execute=Connection.execute
            def broken(connection,statement,*args,**kwargs):
                if isinstance(statement,Update):raise RuntimeError('simulated SQL failure')
                return execute(connection,statement,*args,**kwargs)
            with patch.object(Connection,'execute',broken),self.assertRaises(RuntimeError):database_probe(url,write_test=True)
            self.assertEqual([original],store.list_events())
            with store.engine.connect() as conn:self.assertEqual([],conn.execute(store.cameras.select()).all())
            store.engine.dispose()

    def test_readiness_probe_uses_env_key_and_preserves_503(self):
        import threading
        from types import SimpleNamespace
        from sorting_vision.realtime import create_live_server
        from sorting_vision.diagnostics import readiness_probe
        server=create_live_server(SimpleNamespace(status=lambda:dict(ready=False,status='degraded')),'127.0.0.1',0,'probe-key')
        thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            with patch.dict(os.environ,{'SORTING_API_KEY':'probe-key'}):result=readiness_probe(server.server_port)
            self.assertFalse(result['passed']);self.assertEqual(503,result['http_status'])
        finally:server.shutdown();thread.join();server.server_close()


if __name__=='__main__':unittest.main()
