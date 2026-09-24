import unittest
from types import SimpleNamespace
from unittest.mock import patch
import hapi_bridge
from model import validate
import json
from pathlib import Path


class HapiTests(unittest.TestCase):
    def test_session_id_cannot_inject_commands_or_urls(self):
        for value in ('../other', ';touch /tmp/oops', 'x?token=y', ''):
            with self.assertRaises(ValueError):hapi_bridge.checked_session(value)
        doc=json.loads(Path('examples/demo.json').read_text())
        from model import surfaces
        terminal=next(s for s in surfaces(doc['layout']) if s['type']=='terminal')
        terminal['hapi_session']='../bad'
        with self.assertRaises(ValueError):validate(doc)

    def test_binding_refuses_a_running_agent(self):
        with patch.object(hapi_bridge.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='node\n')):
            with self.assertRaises(ValueError):hapi_bridge.assert_shell({'session':'demo-agent'})

    def test_attachment_resumes_inactive_session_through_runner(self):
        api=object.__new__(hapi_bridge.Hapi)
        inactive={'active':False,'metadata':{'flavor':'codex'}}
        active=dict(inactive,active=True)
        with patch.object(api,'session',side_effect=[inactive,active]),patch.object(api,'request',return_value={'type':'success'}) as request:
            self.assertEqual(api.ready('example-id'),active)
            request.assert_called_once_with('/api/sessions/example-id/resume',{})

    def test_active_session_is_never_spawned_again(self):
        api=object.__new__(hapi_bridge.Hapi)
        with patch.object(api,'session',return_value={'active':True,'metadata':{'flavor':'codex'}}),patch.object(api,'request') as request:
            api.ready('example-id');request.assert_not_called()
