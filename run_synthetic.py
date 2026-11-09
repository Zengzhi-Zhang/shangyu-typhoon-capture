"""Run unchanged original producers on fictional published-size panels."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import sys
import yaml
from synthetic.generate import generate

REPOSITORY = Path(__file__).resolve().parent
OUTPUT = REPOSITORY / 'outputs/synthetic'


def configure(output):
    example = yaml.safe_load((REPOSITORY / 'config/paths.example.yaml').read_text(encoding='utf-8'))
    paths = {key: str(output / 'unused') for key in example['paths']}
    inputs = output / 'inputs'
    paths.update(project_root=str(inputs), v3_root=str(inputs / 'formal_v3'), v6_root=str(inputs / 'formal_v6'), v7_root=str(inputs / 'formal_v7'), v8_root=str(inputs / 'formal_v8'), v9_output_root=str(output / 'formal_v9'), python_executable=sys.executable)
    runtime = output / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    config = runtime / 'paths.yaml'
    config.write_text(yaml.safe_dump({'paths': paths}, sort_keys=True), encoding='utf-8')
    private = runtime / 'private.yaml'
    private.write_text('private: {}\n', encoding='utf-8')
    os.environ['SHANGYU_PATHS_CONFIG'] = str(config)
    os.environ['SHANGYU_PRIVATE_CONFIG'] = str(private)
    os.environ['SHANGYU_SYNTHETIC'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ.setdefault('MPLCONFIGDIR', str(runtime / 'matplotlib'))
    sys.dont_write_bytecode = True
    for round_name in ['v1', 'v3', 'v6', 'v7', 'v9']:
        sys.path.insert(0, str(REPOSITORY / 'analysis' / round_name))
    sys.path.insert(0, str(REPOSITORY))
    return inputs


def analysis_hashes():
    return {path.relative_to(REPOSITORY).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((REPOSITORY / 'analysis').rglob('*')) if path.is_file() and '__pycache__' not in path.parts}


def run(output=OUTPUT):
    output = Path(output).resolve()
    # Never recursively remove an arbitrary CLI path. Both measured runs use
    # exactly this ignored subtree and recreate every generated input/cache.
    if output != OUTPUT.resolve() or not output.is_relative_to(REPOSITORY.resolve()):
        raise RuntimeError('Only the repository outputs/synthetic directory is allowed')
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    before = analysis_hashes()
    inputs = configure(output)
    generate(inputs)
    from synthetic.original_chain import run_original_chain
    result = run_original_chain(inputs, output)
    after = analysis_hashes()
    if before != after:
        raise RuntimeError('An original analysis file changed during execution')
    result['analysis_files'] = len(before)
    result['analysis_sha256_unchanged'] = True
    result['analysis_sha256'] = before
    (output / 'chain_status.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUTPUT)
    result = run(parser.parse_args().output)
    print(json.dumps({'synthetic_run_completed': True, 'core_chain_claim': result['core_chain_claim'], 'Table1_rows': result['Table1_rows'], 'T40_rows': result['T40_rows'], 'T39_rows': result['T39_rows']}))
