"""Load explicitly selected local credentials as literal data, never shell code."""
from pathlib import Path


def load_runtime_env(path=None):
    if path is None:
        return
    if not Path(path).is_file():
        raise ValueError('Environment file is missing')
    from dotenv import load_dotenv
    load_dotenv(path, override=True, interpolate=False, encoding='utf-8')
