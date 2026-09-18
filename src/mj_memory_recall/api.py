"""Bounded WSGI interface; storage and reviewer authority belong to the host."""
from copy import deepcopy
import json

from bangel.diagnostics import BangelDiagnostic
from .engine import (PROFILE, catalog_index, recall, project_selection, shape,
                     validate, review_binding, selection, identifier, _shard)
from .transport import MAX_BODY_BYTES, load_json_bytes

MAX_RESPONSE_BYTES = 1048576


def profile():
    return {'name': 'MJ Memory Recall', 'version': '0.1.0', 'request_profile': PROFILE,
        'status': 'PROVISIONAL', 'routes': ['GET /v1/profile', 'GET /v1/catalog',
            'POST /v1/recall', 'POST /v1/project'],
        'review': 'SERVER_CALLBACK_ONLY; absent independent review remains HOLD',
        'limits': {'request_bytes': MAX_BODY_BYTES, 'response_bytes': MAX_RESPONSE_BYTES,
            'memories': 16, 'query_events': 9, 'trace_events_per_memory': 99},
        'storage': 'Host-bound EpisodicStore; no HTTP storage mutation',
        'r0': {'marker': 'r0', 'status': 'PROVISIONAL', 'mapped_to_R0': False,
            'biological_state': False}, 'physical_actuation_allowed': False,
        'model_updated': False, 'program_profile_changed': False}


def _response(start_response, status, value, extra=()):
    raw = json.dumps(value, separators=(',', ':'), allow_nan=False, ensure_ascii=False).encode('utf-8')
    if len(raw) > MAX_RESPONSE_BYTES:
        status = '500 Internal Server Error'
        raw = b'{"error":{"code":"OUTPUT_LIMIT","message":"Response exceeds its bound"}}'
    start_response(status, [('Content-Type', 'application/json; charset=utf-8'),
        ('Content-Length', str(len(raw))), ('Cache-Control', 'no-store'),
        ('X-Content-Type-Options', 'nosniff')] + list(extra))
    return [raw]


def _error(start_response, status, code, message, extra=()):
    return _response(start_response, status, {'error': {'code': code, 'message': message}}, extra)


def create_app(*, review_provider=None):
    """A caller-supplied, authenticated host callback reviews a copied request.

    No socket is opened. Run behind the ecosystem's own authenticated service.
    A client cannot install reviewers, update models, or select storage paths.
    """
    if review_provider is not None and not callable(review_provider):
        raise TypeError('review_provider must be callable or None')

    def application(environ, start_response):
        path, method = environ.get('PATH_INFO', ''), environ.get('REQUEST_METHOD', '')
        routes = {'/v1/profile': 'GET', '/v1/catalog': 'GET', '/v1/recall': 'POST', '/v1/project': 'POST'}
        if path not in routes:
            return _error(start_response, '404 Not Found', 'NOT_FOUND', 'Unknown route')
        if method != routes[path]:
            return _error(start_response, '405 Method Not Allowed', 'METHOD_NOT_ALLOWED',
                'Method not allowed', [('Allow', routes[path])])
        if environ.get('QUERY_STRING', ''):
            return _error(start_response, '400 Bad Request', 'QUERY_NOT_ALLOWED', 'Closed API profile')
        if path == '/v1/profile':
            return _response(start_response, '200 OK', profile())
        if path == '/v1/catalog':
            return _response(start_response, '200 OK', {'profile': 'MJ-Playbook-Catalog/0.1.0',
                'frame': catalog_index()['frame'], 'coverage': _shard('coverage.json'),
                'selection_ids': sorted(catalog_index()['selections'])})
        media = [part.strip().lower() for part in environ.get('CONTENT_TYPE', '').split(';')]
        if media[0] != 'application/json' or any(p not in ('charset=utf-8', 'charset="utf-8"') for p in media[1:]):
            return _error(start_response, '415 Unsupported Media Type', 'UNSUPPORTED_MEDIA_TYPE', 'Use UTF-8 JSON')
        size = environ.get('CONTENT_LENGTH', '')
        if not size:
            return _error(start_response, '411 Length Required', 'LENGTH_REQUIRED', 'Content-Length required')
        if type(size) is not str or not size.isascii() or not size.isdigit():
            return _error(start_response, '400 Bad Request', 'INVALID_LENGTH', 'Invalid Content-Length')
        if len(size) > 5 or int(size) > MAX_BODY_BYTES:
            return _error(start_response, '413 Content Too Large', 'INPUT_LIMIT', 'Input exceeds 65536 bytes')
        try:
            raw = environ['wsgi.input'].read(int(size))
            if type(raw) is not bytes or len(raw) != int(size):
                raise ValueError('Truncated request')
            request = load_json_bytes(raw)
            if path == '/v1/recall':
                validate(request)
            else:
                shape(request, ('profile', 'selection_id'), 'projection')
                if request['profile'] != 'MJ-Playbook-Projection/0.1.0':
                    raise ValueError('Unsupported projection profile')
                identifier(request['selection_id'], 'selection_id')
                selection(request['selection_id'])
        except (KeyError, OSError, UnicodeError, ValueError, RecursionError, TypeError):
            return _error(start_response, '400 Bad Request', 'INVALID_REQUEST', 'Closed request profile violated')
        review = None
        if path == '/v1/recall':
            try:
                review = None if review_provider is None else review_provider(deepcopy(request))
                review_binding(request, review)
            except Exception:
                return _error(start_response, '503 Service Unavailable', 'REVIEW_UNAVAILABLE', 'Independent review unavailable')
        try:
            result = recall(request, review=review) if path == '/v1/recall' else project_selection(request['selection_id'])
        except (ValueError, RecursionError, BangelDiagnostic):
            return _error(start_response, '422 Unprocessable Content', 'EXECUTION_REJECTED', 'Native execution rejected input')
        except Exception:
            return _error(start_response, '500 Internal Server Error', 'EXECUTION_FAILED', 'Native execution failed')
        return _response(start_response, '200 OK', result)
    return application


application = create_app()
