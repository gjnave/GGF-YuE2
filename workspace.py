"""Browser-owned workspace; only app-owned paths may be restored to Gradio."""
import json
from pathlib import Path
import re
import shutil
import threading
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
WORK = ROOT/'jobs'/'workspaces'
GUARD = threading.Lock()
KEYS = ['style','lyrics','cot','seed','quant','output_format','save_abc','instrumental','strength']


def token(value):
    return value if isinstance(value,str) and re.fullmatch(r'[a-f0-9]{32}',value) else uuid4().hex


def owned(value):
    if not value:
        return None
    path=Path(value).resolve()
    if path.is_file() and any(path.is_relative_to(base.resolve()) for base in (ROOT/'outputs',WORK)):
        return str(path)
    return None


def read(key):
    try:
        return json.loads((WORK/token(key)/'workspace.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {}


def save(key, values=None, **extra):
    key=token(key)
    folder=WORK/key
    with GUARD:
        folder.mkdir(parents=True,exist_ok=True)
        data=read(key)
        if values is not None:
            data.update(dict(zip(KEYS,values)))
        data.update(extra)
        # Atomic replacement, not deletion; a partially written JSON never becomes the workspace.
        temp=folder/'workspace.pending'
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(folder/'workspace.json')
    return key


def retain_abc(key,path):
    key=token(key)
    if not path:
        save(key,abc=None)
        return None
    source=Path(path)
    if source.stat().st_size>2_000_000 or source.suffix.lower()!='.abc':
        raise ValueError('Choose an ABC file smaller than 2 MB.')
    folder=WORK/key
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/f'input-{uuid4().hex[:8]}.abc'
    shutil.copy2(source,target)
    save(key,abc=str(target))
    return str(target)
