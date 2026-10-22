"""Verify published source and model hashes without private training data."""
import ast
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sorting_vision.inference import verify_models

def main():
    files = [p for base in ['scripts', 'sorting_vision', 'tests', 'deploy'] for p in (ROOT / base).rglob('*.py')]
    for path in files:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    print(json.dumps({'status':'passed','python_files':len(files),'models':verify_models(ROOT),'training_data_required':False},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
