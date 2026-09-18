from copy import deepcopy
import io
import json
import unittest

from mj_memory_recall.api import create_app
from mj_memory_recall.engine import request_digest, project_selection, catalog_index
from test_recall import request


def call(app, path, body=None, **overrides):
    raw = json.dumps(body).encode() if not isinstance(body, bytes) else body
    raw = raw or b''
    env = {'PATH_INFO': path, 'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': 'application/json',
        'CONTENT_LENGTH': str(len(raw)), 'wsgi.input': io.BytesIO(raw)}
    env.update(overrides)
    response = []
    content = b''.join(app(env, lambda status, headers: response.append((status, headers))))
    return response[0][0], json.loads(content)


class APITests(unittest.TestCase):
    def test_independent_review_is_required_and_binds_original_request(self):
        value = request()
        status, result = call(create_app(), '/v1/recall', value)
        self.assertEqual(status, '200 OK')
        self.assertFalse(result['advisory_ready'])
        def reviewer(copied):
            digest = request_digest(copied)
            copied['query']['entity'] = 'modified-by-reviewer'
            return {'profile': 'MJ-Memory-Review/0.1.0', 'request_sha256': digest, 'verdict': 'PASS'}
        status, reviewed = call(create_app(review_provider=reviewer), '/v1/recall', value)
        self.assertEqual(status, '200 OK')
        self.assertTrue(reviewed['advisory_ready'])
        self.assertEqual(reviewed['request_sha256'], request_digest(value))

    def test_embedded_authority_and_duplicate_json_are_rejected(self):
        value = request(); value['review'] = {'verdict': 'PASS'}
        self.assertEqual(call(create_app(), '/v1/recall', value)[0], '400 Bad Request')
        self.assertEqual(call(create_app(), '/v1/recall', b'{"profile":"a","profile":"b"}')[0], '400 Bad Request')

    def test_review_failure_and_changed_request_remain_unavailable(self):
        value = request()
        def reviewer(_):
            return {'profile': 'MJ-Memory-Review/0.1.0', 'request_sha256': '0' * 64, 'verdict': 'PASS'}
        status, result = call(create_app(review_provider=reviewer), '/v1/recall', value)
        self.assertEqual(status, '503 Service Unavailable')
        self.assertNotIn('candidate', result)

    def test_transport_bounds_and_method(self):
        app = create_app()
        self.assertEqual(call(app, '/v1/recall', b'', CONTENT_LENGTH='65537')[0], '413 Content Too Large')
        self.assertEqual(call(app, '/v1/recall', b'{}', CONTENT_LENGTH='10')[0], '400 Bad Request')
        self.assertEqual(call(app, '/v1/recall', {}, REQUEST_METHOD='GET')[0], '405 Method Not Allowed')
        self.assertEqual(call(app, '/v1/recall', {}, QUERY_STRING='review=PASS')[0], '400 Bad Request')

    def test_catalog_and_all_actor_projection(self):
        status, result = call(create_app(), '/v1/catalog', REQUEST_METHOD='GET')
        self.assertEqual(status, '200 OK')
        self.assertEqual(len(result['selection_ids']), 1080)
        value = project_selection(result['selection_ids'][0])
        self.assertEqual(len(value['paths']), 11)
        self.assertEqual(len({p['actor'] for p in value['paths']}), 11)
        self.assertTrue(all(len(p['nodes']) == 9 and all(1 <= n <= 9 for n in p['nodes']) for p in value['paths']))
        self.assertFalse(value['physical_actuation_allowed'])
