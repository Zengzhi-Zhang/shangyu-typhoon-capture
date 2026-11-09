# -*- coding: utf-8 -*-
"""Syntax-only validation before root permits numerical execution."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json
root=Path(_release_path('v6_root'))
names=['spatial_helpers_v6.py','device_state_v6.py','s_pre_v6.py','inspect_state_inputs_v6.py','audit_spatial_v6.py','audit_public_spatial_v6.py']
for name in names:
    p=root/'scripts'/name
    compile(p.read_text(encoding='utf-8'),str(p),'exec')
json.loads((root/'00_env/interpretation_spatial_v6.json').read_text(encoding='utf-8'))
print(json.dumps(dict(syntax_passed=names,interpretation_valid_json=True,numerical_analysis_run=False)))
