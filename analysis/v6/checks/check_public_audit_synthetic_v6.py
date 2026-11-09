# -*- coding: utf-8 -*-
"""Synthetic tests for independent token and Decimal privacy checks."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
from audit_public_spatial_v6 import identifier_tokens, excess_precision, json_coordinate_precision
from spatial_helpers_v6 import ROOT, now, write_json


def main():
    checks = {
        'fraction_digits_excluded': identifier_tokens(_release_private('private_value_005')) == [],
        'negative_fraction_digits_excluded': identifier_tokens(_release_private('private_value_006')) == [],
        'independent_integer_retained': identifier_tokens(_release_private('private_value_007')) == [_release_private('private_value_007')],
        'hex_with_letter_retained': identifier_tokens(_release_private('private_value_008')) == [_release_private('private_value_009')],
        'mixed_hex_after_dot_retained': identifier_tokens(_release_private('private_value_010')) == [_release_private('private_value_011')],
        'uppercase_hex_retained': identifier_tokens(_release_private('private_value_012')) == [_release_private('private_value_012')],
        'embedded_alphanumeric_excluded': identifier_tokens(_release_private('private_value_013')) == [],
        'independent_integer_after_sentence_retained': identifier_tokens(_release_private('private_value_014')) == [_release_private('private_value_007')],
        'two_decimal_coordinates_allowed': not excess_precision('120.31') and not excess_precision('30.00'),
        'third_decimal_coordinate_rejected': excess_precision('120.311'),
        'trailing_third_decimal_strictly_rejected': excess_precision('120.310'),
        'scientific_decimal_precision_rejected': excess_precision('1.20311e2'),
        'coordinate_missing_allowed': all(not excess_precision(x) for x in ('NA', '', 'null')),
        'JSON_preserves_long_coordinate_decimal': json_coordinate_precision('{"lon":120.30000000000000000001}') == 1,
        'JSON_two_decimal_coordinates_allowed': json_coordinate_precision('{"lon":120.30,"nested":[{"plot_lat":30.00}]}') == 0,
        'JSON_scientific_coordinate_precision_rejected': json_coordinate_precision('{"longitude":1.20311e2}') == 1,
    }
    failed = [k for k, v in checks.items() if not v]
    result = dict(ended=now(), all_passed=not failed, n_checks=len(checks), checks=checks,
                  failed=failed, scope='Synthetic strings only; no result/source/key reads')
    write_json(ROOT/'00_env/public_audit_synthetic_checks_v6.json', result)
    print(json.dumps(dict(all_passed=not failed, n_checks=len(checks), failed=failed)))
    if failed:
        raise AssertionError('Synthetic public audit checks failed')


if __name__ == '__main__':
    main()
