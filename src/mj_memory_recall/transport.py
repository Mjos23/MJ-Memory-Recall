"""Shared bounded JSON transport; no source text or reviewer policy is interpreted."""
import json

MAX_BODY_BYTES = 65536


def load_json_bytes(raw):
    if type(raw) is not bytes:
        raise ValueError('Input must be UTF-8 JSON bytes')
    if len(raw) > MAX_BODY_BYTES:
        raise ValueError('Input exceeds 65536 bytes')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('Nonfinite JSON value: ' + value)

    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid)
    except RecursionError as error:
        raise ValueError('JSON nesting exceeds the transport bound') from error
