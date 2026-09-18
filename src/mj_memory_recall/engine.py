"""Validate and bind inputs; all scoring, geometry and decisions run in Bangel."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import time

from bangel.compiler import ElsaCompiler
from bangel.ir import JPIR
from bangel.runtime import JoannaRuntime
from bangel.receipts import verify_receipt

HERE = Path(__file__).resolve().parent
PROFILE = 'MJ-Memory-Recall/0.1.0'
COMMANDS = ('let', 'measure', 'derive', 'require', 'if', 'for', 'match', 'emit', 'return')
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z')
DECIMAL = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?\Z')
LIMITS = dict(instruction_limit=50000, event_limit=50000, function_depth=64,
    evaluation_limit=1000000, allocation_limit=16000000, output_limit=1048576,
    receipt_limit=16777216)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False,
                      ensure_ascii=False)


def request_digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def shape(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(label + ': unexpected or missing fields')


def identifier(value, label):
    if type(value) is not str or not IDENTIFIER.fullmatch(value):
        raise ValueError(label + ': invalid identifier')
    return value


def integer(value, label, maximum=9007199254740991):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(label + ': invalid nonnegative integer')
    return value


def real(value, label, low='-1000000', high='1000000'):
    if type(value) is not str or len(value) > 28 or not DECIMAL.fullmatch(value):
        raise ValueError(label + ': finite decimal string required')
    if not Decimal(low) <= Decimal(value) <= Decimal(high):
        raise ValueError(label + ': out of range')
    return value if '.' in value else value + '.0'


def vector(value, count, label, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= count:
        raise ValueError(label + ': invalid bounded list')


def validate_frame(frame):
    shape(frame, ('id', 'x_min', 'y_min', 'width', 'height'), 'frame')
    identifier(frame['id'], 'frame.id')
    for key in ('x_min', 'y_min'):
        real(frame[key], 'frame.' + key)
    for key in ('width', 'height'):
        real(frame[key], 'frame.' + key, '0.000001')


def validate_position(position, frame):
    if position is None:
        return
    vector(position, 2, 'position', 2)
    for axis, lower, span in [(0, 'x_min', 'width'), (1, 'y_min', 'height')]:
        real(position[axis], 'position')
        if not Decimal(frame[lower]) <= Decimal(position[axis]) <= Decimal(frame[lower]) + Decimal(frame[span]):
            raise ValueError('Position is outside its declared coordinate frame')


def validate_events(events, frame, maximum):
    vector(events, maximum, 'events')
    seen = set()
    for event in events:
        shape(event, ('actor', 'step', 'position', 'command'), 'event')
        identifier(event['actor'], 'event.actor')
        integer(event['step'], 'event.step', 8)
        key = (event['actor'], event['step'])
        if key in seen:
            raise ValueError('Duplicate event actor/step')
        seen.add(key)
        validate_position(event['position'], frame)
        if event['command'] is not None and event['command'] not in COMMANDS:
            raise ValueError('Unknown command token')


def validate(request):
    shape(request, ('profile', 'namespace', 'as_of', 'frame', 'memories', 'query'), 'request')
    if request['profile'] != PROFILE:
        raise ValueError('Unsupported recall profile')
    identifier(request['namespace'], 'namespace')
    integer(request['as_of'], 'as_of')
    validate_frame(request['frame'])
    query = request['query']
    shape(query, ('id', 'observed_at', 'cue', 'entity', 'relation', 'context', 'previous_command', 'events'), 'query')
    identifier(query['id'], 'query.id')
    integer(query['observed_at'], 'query.observed_at')
    if query['observed_at'] != request['as_of']:
        raise ValueError('as_of must equal the first query observation')
    if query['previous_command'] not in COMMANDS:
        raise ValueError('Unknown previous command')
    vector(query['cue'], 9, 'cue', 9)
    for value in query['cue']:
        if value is not None:
            real(value, 'cue', '-0.9', '0.9')
    for key in ('entity', 'relation', 'context'):
        if query[key] is not None:
            identifier(query[key], 'query.' + key)
    validate_events(query['events'], request['frame'], 9)
    vector(request['memories'], 16, 'memories', 1)
    ids = {query['id']}
    for memory in request['memories']:
        shape(memory, ('id', 'namespace', 'pattern', 'entity', 'relation', 'context',
            'observed_at', 'available_at', 'provenance', 'receipt_ref', 'selection_id', 'trace'), 'memory')
        for key in ('id', 'namespace', 'entity', 'relation', 'context', 'receipt_ref'):
            identifier(memory[key], 'memory.' + key)
        if memory['id'] in ids:
            raise ValueError('Duplicate memory/query identity')
        ids.add(memory['id'])
        if memory['namespace'] != request['namespace']:
            raise ValueError('Memory belongs to another namespace')
        for key in ('observed_at', 'available_at'):
            integer(memory[key], 'memory.' + key)
        if not memory['observed_at'] <= memory['available_at'] < request['as_of']:
            raise ValueError('Memory was unavailable at first query observation')
        if memory['provenance'] != 'OBSERVED':
            raise ValueError('Synthetic/coached records cannot act as observed memories')
        vector(memory['pattern'], 9, 'pattern', 9)
        for value in memory['pattern']:
            real(value, 'pattern', '-0.9', '0.9')
            if Decimal(value) not in (Decimal('-0.9'), Decimal('0.9')):
                raise ValueError('Memory patterns must be bipolar +/-0.9')
        validate_events(memory['trace'], request['frame'], 99)
        if memory['selection_id'] is not None:
            identifier(memory['selection_id'], 'selection_id')
            if request['frame'] != catalog_index()['frame']:
                raise ValueError('Playbook curves require their original schematic coordinate frame')
            selection(memory['selection_id'])
    return request


@lru_cache(maxsize=1)
def catalog_index():
    return json.loads((HERE / 'data/index.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=128)
def _shard(name):
    index = catalog_index()
    if name not in index['shard_sha256']:
        raise ValueError('Unknown packaged catalog shard')
    raw = (HERE / 'data' / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != index['shard_sha256'][name]:
        raise ValueError('Playbook shard digest mismatch')
    return json.loads(raw)


def selection(key):
    name = catalog_index()['selections'].get(key)
    if name is None:
        raise ValueError('Unknown playbook selection')
    for item in _shard(name)['selections']:
        if item['id'] == key:
            return deepcopy(item)
    raise ValueError('Catalog selection index mismatch')


# Project-specific operator binding, distinct from the playbook's own syntax.
# The source path and responsibility labels remain available in the catalog.
COMMAND_BY_PATH = {
    'BLOCK_TRACK': 'require', 'RUN_SUPPORT_BLOCK': 'require',
    'PROTECTION_SET': 'require', 'RUN_TRACK': 'derive', 'PULL_TRACK': 'for',
    'MESH_READ': 'measure', 'DROP_LAUNCH': 'let', 'CROSSING_ROUTE': 'for',
    'RPO_ACCESS_ROUTE': 'if', 'RUSH_OR_FIT_TRACK': 'if',
    'FIT_OR_PRESSURE_ENTRY': 'if', 'HOOK_WALL_DROP': 'match',
    'MAN_LEVERAGE': 'match', 'CLOUD_OR_FLAT_LEVERAGE': 'measure',
    'DEEP_ZONE_DISTRIBUTION': 'emit', 'SCAN_RELEASE': 'match',
    'SCREEN_BLOCK_OR_RELEASE': 'if', 'SCREEN_RELEASE': 'emit',
    'SLANT_FLAT_DISTRIBUTION': 'for', 'TIMED_ROUTE': 'measure',
    'VERTICAL_STEM': 'derive', 'MISSING': 'measure',
}


def path_command(kind):
    if kind not in COMMAND_BY_PATH:
        raise ValueError('Unmapped playbook path kind')
    return COMMAND_BY_PATH[kind]


def txt(value):
    return json.dumps(value, ensure_ascii=False)


def optional(value):
    return ('Result.Err(Failure(code = "MISSING", message = "Unobserved"))' if value is None
            else 'Result.Ok(' + txt(value) + ')')


def point(value):
    return 'recall.Point(x = ' + real(str(value[0]), 'point.x') + ', y = ' + real(str(value[1]), 'point.y') + ')'


def position(value):
    return ('recall.Position.Missing(reason = "Unobserved position")' if value is None else
            'recall.Position.Known(point = ' + point(value) + ')')


def event(value):
    return ('recall.Event(actor = ' + txt(value['actor']) + ', step = ' + str(value['step']) +
            ', position = ' + position(value['position']) + ', command = ' + optional(value['command']) + ')')


def curve(value):
    return ('recall.Curve(start = ' + point(value['start']) + ', control = ' + point(value['control']) +
            ', finish = ' + point(value['end']) + ', command = ' + txt(path_command(value['kind'])) + ')')


def frame_source(frame):
    return 'recall.Frame(' + ', '.join(key + ' = ' + real(frame[key], key) for key in
                                      ('x_min', 'y_min', 'width', 'height')) + ')'


def review_binding(request, review):
    if review is None:
        return False, 'HOLD'
    shape(review, ('profile', 'request_sha256', 'verdict'), 'review')
    if (review['profile'] != 'MJ-Memory-Review/0.1.0' or
        review['request_sha256'] != request_digest(request) or review['verdict'] not in ('PASS', 'HOLD', 'DENY')):
        raise ValueError('Review is invalid or belongs to another request')
    return True, review['verdict']


def source_files(request, *, review=None):
    validate(request)
    reviewed, verdict = review_binding(request, review)
    query = request['query']
    episodes = []
    empty_curve = {'start': [0, 0], 'control': [0, 0], 'end': [0, 0], 'kind': 'MISSING'}
    for memory in request['memories']:
        remembered = {(e['actor'], e['step']): e for e in memory['trace']}
        paths = {} if memory['selection_id'] is None else {
            item['actor']: item for item in selection(memory['selection_id'])['paths']}
        aligned = []
        for observation in query['events']:
            past = remembered.get((observation['actor'], observation['step']),
                dict(actor=observation['actor'], step=observation['step'], position=None, command=None))
            path = paths.get(observation['actor'])
            aligned.append('recall.Aligned(observation = ' + event(observation) + ', remembered = ' + event(past) +
                ', has_curve = ' + str(path is not None).lower() + ', curve = ' + curve(path or empty_curve) + ')')
        fields = [key + ' = ' + txt(memory[key]) for key in ('id', 'namespace', 'entity', 'relation', 'context')]
        fields += [key + ' = ' + str(memory[key]) for key in ('observed_at', 'available_at')]
        fields += ['pattern = [' + ', '.join(real(x, 'pattern') for x in memory['pattern']) + ']',
                   'aligned = [' + ', '.join(aligned) + ']']
        episodes.append('recall.Episode(' + ', '.join(fields) + ')')
    features = ['recall.Feature.Missing(reason = "Unobserved cue")' if value is None else
                'recall.Feature.Known(value = ' + real(value, 'cue') + ')' for value in query['cue']]
    history = []
    for memory in sorted(request['memories'], key=lambda item: (item['available_at'], item['id'])):
        actors = {}
        for item in memory['trace']:
            actors.setdefault(item['actor'], []).append(item)
        for actor in sorted(actors):
            values = sorted(actors[actor], key=lambda item: item['step'])
            for first, second in zip(values, values[1:]):
                if second['step'] == first['step'] + 1 and first['command'] is not None and second['command'] is not None:
                    history.append('recall.Transition(previous = ' + txt(first['command']) + ', following = ' + txt(second['command']) + ')')
    # A documented latest-128 observation window, never bridged across missing steps.
    history = history[-128:]
    arguments = ', '.join(optional(query[k]) for k in ('entity', 'relation', 'context'))
    lines = ['bangel 1.0', 'program mj_memory_recall', 'effects pure', 'import mj.recall as recall',
        'let memories: Vector[recall.Episode] = [' + ', '.join(episodes) + ']',
        'let cue: Vector[recall.Feature; 9] = [' + ', '.join(features) + ']',
        'let frame = ' + frame_source(request['frame']),
        'let history: Vector[recall.Transition] = [' + ', '.join(history) + ']',
        'let attempt = recall.retrieve(memories, cue, frame, ' + txt(request['namespace']) + ', ' +
            str(request['as_of']) + ', ' + arguments + ')',
        'match attempt', '  case Result.Ok(result)', '    emit retrieval = result',
        'emit request_sha256 = ' + txt(request_digest(request)),
        'emit review_status = recall.review_status(result.matched, ' + str(reviewed).lower() + ', ' + txt(verdict) + ')',
        '  case Result.Err(error)', '    require false else RECALL_NATIVE_INPUT', 'end',
        'emit original_cue = cue', 'emit profile = ' + txt(PROFILE),
        'emit forecast = recall.forecast(history, ' + txt(query['previous_command']) + ')']
    return {'recall.bangel': (HERE / 'source/recall.bangel').read_text(encoding='utf-8'),
            'main.bangel': '\n'.join(lines) + '\n'}


def plain(value):
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        if value.get('kind') == 'int':
            return int(value['value'])
        if value.get('kind') == 'real':
            return value['value']
        if value.get('kind') == 'record':
            return {key: plain(v) for key, v in value['fields'].items()}
        return {key: plain(v) for key, v in value.items()}
    return value


def execute(sources):
    raw = ElsaCompiler().compile_project(sources, entry_source_name='main.bangel').to_bytes()
    admitted = JPIR.from_bytes(raw)
    admitted.verify()
    deadline = time.monotonic() + 45
    receipt = JoannaRuntime(**LIMITS).execute(admitted.to_dict(),
        cancelled=lambda: time.monotonic() > deadline).to_dict()
    verify_receipt(receipt)
    if receipt['status'] != 'PASS':
        raise ValueError('Recall execution did not pass: ' + str(receipt['hold_code']))
    if receipt['authority_effect'] != 'NONE' or receipt['physical_effect'] != 'NONE':
        raise ValueError('Unexpected recall authority or physical effect')
    return raw, receipt


def recall(request, *, review=None, include_receipt=False):
    request = deepcopy(request)
    sources = source_files(request, review=deepcopy(review))
    raw, receipt = execute(sources)
    outputs = plain(receipt['outputs'])
    retrieved = outputs['retrieval']
    result = {'profile': PROFILE, 'name': 'MJ Memory Recall', 'namespace': request['namespace'],
        'status': retrieved['status'],
        'candidate': retrieved['candidate']['id'] if retrieved['available'] else None,
        'candidate_available': retrieved['available'], 'match_available': retrieved['matched'],
        'baseline_available': retrieved['baseline_available'],
        'baseline_candidate': retrieved['baseline_id'] if retrieved['baseline_available'] else None,
        'known_features': retrieved['known'], 'scores': retrieved['candidate'],
        'margin': retrieved['margin'], 'original_cue': outputs['original_cue'],
        'forecast': outputs['forecast'],
        'review_status': outputs['review_status'], 'advisory_ready': outputs['review_status'] == 'MATCH_FOR_REVIEW',
        'r0': {'marker': 'r0', 'profile': 'MJ-Neural-r0/0.1.0', 'status': 'PROVISIONAL', 'mapped_to_R0': False, 'biological_state': False},
        'request_sha256': request_digest(request), 'jp_sha256': hashlib.sha256(raw).hexdigest(),
        'receipt_root': receipt['receipt_root'], 'resources': receipt['resource_limits'],
        'source_sha256': {key: hashlib.sha256(value.encode()).hexdigest() for key, value in sources.items()},
        'physical_actuation_allowed': False, 'live_trading_allowed': False,
        'model_updated': False, 'program_profile_changed': False}
    if not result['forecast']['available']:
        result['forecast']['command'] = result['forecast']['node'] = None
    if include_receipt:
        result['receipt'] = receipt
    return result


def project_path(path, frame):
    validate_frame(frame)
    for key in ('start', 'control', 'end'):
        validate_position([str(x) for x in path[key]], frame)
    sources = {'recall.bangel': (HERE / 'source/recall.bangel').read_text(encoding='utf-8'),
        'main.bangel': '\n'.join(['bangel 1.0', 'program mj_memory_projection', 'effects pure',
            'import mj.recall as recall', 'emit path = recall.projected_path(' + curve(path) + ', ' +
            frame_source(frame) + ')']) + '\n'}
    raw, receipt = execute(sources)
    output = plain(receipt['outputs'])['path']
    if output.get('kind') != 'result' or output.get('variant') != 'Ok':
        raise ValueError('Native path projection rejected the geometry')
    return {'nodes': output['value'], 'jp_sha256': hashlib.sha256(raw).hexdigest(),
            'receipt_root': receipt['receipt_root']}


def project_selection(selection_id):
    """Project all eleven original actor paths in one admitted native execution."""
    identifier(selection_id, 'selection_id')
    item = selection(selection_id)
    frame = catalog_index()['frame']
    sources = {'recall.bangel': (HERE / 'source/recall.bangel').read_text(encoding='utf-8'),
        'main.bangel': '\n'.join(['bangel 1.0', 'program mj_playbook_projection', 'effects pure',
            'import mj.recall as recall', 'let frame = ' + frame_source(frame)] + [
                'emit actor_' + str(index) + ' = recall.projected_path(' + curve(path) + ', frame)'
                for index, path in enumerate(item['paths'])]) + '\n'}
    raw, receipt = execute(sources)
    outputs = plain(receipt['outputs'])
    paths = []
    for index, path in enumerate(item['paths']):
        output = outputs['actor_' + str(index)]
        if output.get('kind') != 'result' or output.get('variant') != 'Ok':
            raise ValueError('Native projection rejected a packaged curve')
        paths.append(dict(actor=path['actor'], group=path['group'], kind=path['kind'],
            nodes=output['value'], command=path_command(path['kind']),
            start=path['start'], control=path['control'], end=path['end']))
    return {'profile': 'MJ-Playbook-Projection/0.1.0', 'selection_id': selection_id,
        'frame': deepcopy(frame), 'sampling': 't = step / 8; step 0..8; repeated nodes preserved',
        'node_namespace': 'MJ.Engineered.Spatial.N1-N9', 'paths': paths,
        'read_rules': item['read_rules'], 'sequence_links': item['sequence_links'],
        'source': item['source'], 'jp_sha256': hashlib.sha256(raw).hexdigest(),
        'receipt_root': receipt['receipt_root'], 'physical_actuation_allowed': False}
