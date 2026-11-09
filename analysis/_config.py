"""Configuration access for the otherwise unchanged historical analysis code."""
from pathlib import Path
import os
import yaml

_REPOSITORY = Path(__file__).resolve().parents[1]
_CACHE = {}

def _load(kind):
    variable = 'SHANGYU_PATHS_CONFIG' if kind == 'paths' else 'SHANGYU_PRIVATE_CONFIG'
    default = _REPOSITORY / 'config' / (kind + '.yaml')
    filename = Path(os.environ.get(variable, str(default))).expanduser()
    signature = (str(filename), filename.stat().st_mtime_ns)
    if _CACHE.get(kind, (None,))[0] != signature:
        with filename.open(encoding='utf-8') as stream:
            data = yaml.safe_load(stream) or {}
        _CACHE[kind] = (signature, data.get(kind, data))
    return _CACHE[kind][1]

def configured_path(key):
    """Return one configured path or command string without changing its type."""
    return str(_load('paths')[key])

def private_value(key):
    """Retrieve a restricted keyword, identifier or lookup value unchanged."""
    return _load('private')[key]

def key_file():
    """The key is supplied by its authorised custodian, never by this repository."""
    return os.environ['SHANGYU_HMAC_KEY_FILE']
