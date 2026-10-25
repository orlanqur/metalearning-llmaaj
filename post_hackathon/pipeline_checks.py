"""Offline pipeline reproducibility checks. Run from the repository root."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(os.environ.get('REVIEW_ROOT', '.')).resolve()
def cli(*args):
    p = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stdout + p.stderr)
    return p.stdout
def read_predictions(p):
    with p.open() as f:
        return {r['item_id']:r['label'] for r in csv.DictReader(f)}
def write_rows(p, rows):
    p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

with tempfile.TemporaryDirectory() as temp:
    tmp = Path(temp)
    cli('src/prepare_inputs.py','--train','data/public_train.csv','--test','data/public_test.csv','--out-dir',str(tmp/'inputs'))
    train = tmp/'inputs/train.jsonl'; test = tmp/'inputs/test.jsonl'
    art = tmp/'artifacts'
    cli('-m','solution','adapt','--input',str(train),'--artifacts',str(art),'--no-model')
    before = {str(p.relative_to(art)):hashlib.sha256(p.read_bytes()).hexdigest() for p in art.rglob('*') if p.is_file()}
    out = tmp/'baseline/predictions.csv'
    cli('-m','solution','eval','--input',str(test),'--artifacts',str(art),'--output',str(out),'--no-model')
    expected=read_predictions(out)
    score=json.loads(cli('src/evaluate.py','--test','data/public_test.csv','--predictions',str(out)))
    rows=[json.loads(l) for l in test.read_text().splitlines()]
    results={}
    variants={
      'reverse_order':list(reversed(rows)),
      'injected_test_labels':[dict(r,label='bad' if expected[r['item_id']]=='good' else 'good') for r in rows],
      'renamed_ids':[dict(r,item_id='renamed-'+str(i)) for i,r in enumerate(rows)],
    }
    for name, variant in variants.items():
        inp=tmp/(name+'.jsonl');pred=tmp/name/'predictions.csv';write_rows(inp,variant)
        cli('-m','solution','eval','--input',str(inp),'--artifacts',str(art),'--output',str(pred),'--no-model')
        actual=read_predictions(pred)
        if name=='renamed_ids':
            passed=all(actual['renamed-'+str(i)]==expected[r['item_id']] for i,r in enumerate(rows))
        else:passed=actual==expected
        results[name]=passed
    repeat=tmp/'repeat/predictions.csv'
    cli('-m','solution','eval','--input',str(test),'--artifacts',str(art),'--output',str(repeat),'--no-model')
    results['repeat_identical_prediction_bytes']=repeat.read_bytes()==out.read_bytes()
    after={str(p.relative_to(art)):hashlib.sha256(p.read_bytes()).hexdigest() for p in art.rglob('*') if p.is_file()}
    results['artifacts_unchanged_during_eval']=before==after
    results['exactly_80_unique_predictions']=len(expected)==80
    report={'mode':'deterministic_no_model','results':results,'public_development_score':score,
            'network_calls':json.loads(out.with_suffix('.log.json').read_text())['stats']['network_calls']}
    print(json.dumps(report,indent=2))
    if not all(results.values()):sys.exit(1)
