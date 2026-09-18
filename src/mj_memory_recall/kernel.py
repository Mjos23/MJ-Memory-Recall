"""Transport bindings for pure Bangel lifecycle and candidate qualification."""
from copy import deepcopy
import hashlib
import re

from . import engine

UPDATE_PROFILE = 'MJ-Memory-Update/0.1.0'
REVIEW_PROFILE = 'MJ-Memory-Update-Review/0.1.0'
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
MODEL_FIELDS = ('model_sha256', 'program_profile_sha256', 'game_plan_sha256', 'film_evidence_sha256')


def _hash(value, label):
    if type(value) is not str or not SHA256.fullmatch(value):
        raise ValueError(label + ': lowercase SHA-256 required')
    return value


def _execute(expression):
    sources = {'kernel.bangel': (engine.HERE / 'source/kernel.bangel').read_text(encoding='utf-8'),
        'main.bangel': '\n'.join(['bangel 1.0', 'program mj_memory_kernel', 'effects pure',
            'import mj.memory_kernel as kernel', 'let attempt = ' + expression,
            'match attempt', '  case Result.Ok(value)', '    emit ok = true', '    emit value = value',
            '  case Result.Err(error)', '    emit ok = false', '    emit error = error.code', 'end']) + '\n'}
    raw, receipt = engine.execute(sources)
    result = engine.plain(receipt['outputs'])
    result.update(jp_sha256=hashlib.sha256(raw).hexdigest(), receipt_root=receipt['receipt_root'],
        source_sha256=hashlib.sha256(sources['kernel.bangel'].encode()).hexdigest())
    return result


def _state_source(state):
    engine.shape(state, ('stage', 'generation'), 'state')
    engine.identifier(state['stage'], 'stage')
    engine.integer(state['generation'], 'generation', 1000000)
    return 'kernel.Lifecycle(stage = ' + engine.txt(state['stage']) + ', generation = ' + str(state['generation']) + ')'


def transition(state, action, *, checkpoint_valid=False):
    """Ask the native lifecycle for one transition; never edits persistent state."""
    engine.identifier(action, 'action')
    if type(checkpoint_valid) is not bool:
        raise ValueError('checkpoint_valid must be a host-verified boolean')
    result = _execute('kernel.transition(' + _state_source(state) + ', ' + engine.txt(action) + ', ' + str(checkpoint_valid).lower() + ')')
    if not result['ok']:
        raise ValueError(result['error'])
    return {'state': result['value'], **{k: result[k] for k in ('jp_sha256', 'receipt_root', 'source_sha256')}}


def authorize(state, operation):
    """Ask the native lifecycle whether append/snapshot access is allowed."""
    engine.identifier(operation, 'operation')
    result = _execute('kernel.access(' + _state_source(state) + ', ' + engine.txt(operation) + ')')
    if not result['ok'] or result.get('value') is not True:
        raise ValueError(result.get('error', 'MEMORY_INACTIVE'))
    return {k: result[k] for k in ('jp_sha256', 'receipt_root', 'source_sha256')}


def validate_update(request):
    engine.shape(request, ('profile', 'id', 'namespace', 'as_of', 'baseline', 'candidate', 'signals', 'validation'), 'update')
    if request['profile'] != UPDATE_PROFILE:
        raise ValueError('Unsupported memory update profile')
    for key in ('id', 'namespace'):
        engine.identifier(request[key], key)
    engine.integer(request['as_of'], 'as_of')
    for key in ('baseline', 'candidate'):
        engine.shape(request[key], MODEL_FIELDS, key)
        for field in MODEL_FIELDS:
            _hash(request[key][field], key + '.' + field)
    common = ('id', 'receipt_ref', 'namespace', 'observed_at', 'available_at', 'provenance')
    for split, maximum in (('signals', 64), ('validation', 16)):
        engine.vector(request[split], maximum, split)
        extra = (('classified', 'compatible', 'domain_retention_qualified') if split == 'signals'
                 else ('target', 'prior_prediction', 'candidate_prediction'))
        for item in request[split]:
            engine.shape(item, common + extra, split)
            for field in ('id', 'receipt_ref', 'namespace', 'provenance'):
                engine.identifier(item[field], split + '.' + field)
            for field in ('observed_at', 'available_at'):
                engine.integer(item[field], field)
            for field in extra:
                if split == 'signals':
                    if type(item[field]) is not bool:
                        raise ValueError(field + ': explicit boolean required')
                else:
                    engine.real(item[field], field, '0', '1')
    return request


def _model(model):
    return 'kernel.Model(' + ', '.join(key + ' = ' + engine.txt(model[key]) for key in MODEL_FIELDS) + ')'


def _record(item, name):
    fields = []
    for key, value in item.items():
        if key in ('target', 'prior_prediction', 'candidate_prediction'):
            encoded = engine.real(value, key, '0', '1')
        elif type(value) is bool:
            encoded = str(value).lower()
        elif type(value) is int:
            encoded = str(value)
        else:
            encoded = engine.txt(value)
        fields.append(key + ' = ' + encoded)
    return 'kernel.' + name + '(' + ', '.join(fields) + ')'


def assess_update(request, *, review=None):
    """Assess host-supplied candidate predictions; installs or rewrites nothing.

    Classified/compatible/domain-retention flags and receipt references are host
    evidence claims. Their authenticity remains the independent host's concern.
    """
    request = deepcopy(validate_update(deepcopy(request)))
    review = deepcopy(review)
    reviewed, verdict = False, 'HOLD'
    if review is not None:
        engine.shape(review, ('profile', 'request_sha256', 'verdict'), 'update review')
        if (review['profile'] != REVIEW_PROFILE or review['request_sha256'] != engine.request_digest(request)
                or review['verdict'] not in ('PASS', 'HOLD', 'DENY')):
            raise ValueError('Independent review is invalid or bound to a different candidate request')
        reviewed, verdict = True, review['verdict']
    expression = ('kernel.assess(' + engine.txt(request['id']) + ', ' + engine.txt(request['namespace']) + ', ' + str(request['as_of']) + ', ' +
        _model(request['baseline']) + ', ' + _model(request['candidate']) + ', [' +
        ', '.join(_record(item, 'Signal') for item in request['signals']) + '], [' +
        ', '.join(_record(item, 'Validation') for item in request['validation']) + '], ' +
        str(reviewed).lower() + ', ' + engine.txt(verdict) + ')')
    native = _execute(expression)
    if native['ok']:
        decision = native['value']
        if not decision['loss_evaluated']:
            decision['prior_loss'] = decision['candidate_loss'] = None
    else:
        decision = {'promoted': False, 'reason': native['error'], 'qualified_signals': None,
            'validation_count': None, 'loss_evaluated': False, 'prior_loss': None, 'candidate_loss': None}
    return {'profile': UPDATE_PROFILE, 'namespace': request['namespace'], **decision,
        'request_sha256': engine.request_digest(request),
        'candidate_sha256': request['candidate']['model_sha256'],
        'program_profile_changed': False, 'game_plan_changed': False, 'film_evidence_changed': False,
        'model_installed': False, 'physical_actuation_allowed': False,
        **{key: native[key] for key in ('jp_sha256', 'receipt_root', 'source_sha256')}}
