"""Update from host-generated repository archives; no release ZIP or hash manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent
PRIVATE = {'.git','.venv','.venv-3.12','.gradio','models','runtime','downloads','outputs','jobs','logs','__pycache__',
           'network_settings.json','local_settings.json','app.lock','.installed-revision.json'}
MARKER = '.installed-revision.json'

def config(root):
    return json.loads((root/'release_sources.json').read_text(encoding='utf-8'))

def read_url(url):
    with urlopen(Request(url,headers={'User-Agent':'GGF-App-Updater','Cache-Control':'no-cache'}),timeout=30) as response:
        return response.read()

def latest(source):
    value=json.loads(read_url(source['api']))
    sha=value.get('sha') or value.get('commit',{}).get('id')
    if not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{40,64}',sha):
        raise ValueError('Repository returned an invalid revision.')
    return sha

def installed(root):
    try:
        return json.loads((root/MARKER).read_text())['revision']
    except (OSError,ValueError,KeyError):
        if (root/'.git').exists() and shutil.which('git'):
            result=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,timeout=10)
            if result.returncode==0:
                return result.stdout.strip()
    return None

def check_update(root=ROOT):
    errors=[]
    for source in config(root)['mirrors']:
        try:
            sha=latest(source)
            if sha==installed(root):
                return f"Up to date ({sha[:8]}, {source['name']})."
            return f"**Update available from {source['name']}.** Use Update and restart, or close the app and run its update BAT. Models, settings and results are kept."
        except Exception as error:
            errors.append(f"{source['name']}: {error}")
    return 'Could not reach the update repositories. Try again later. ' + '; '.join(errors)

def safe_name(name):
    parts=PurePosixPath(name).parts
    return bool(parts) and not name.startswith(('/','\\')) and '\\' not in name and ':' not in name and '..' not in parts and parts[0] not in PRIVATE and '__pycache__' not in parts

def stage_archive(archive,stage,required):
    """Validate the complete archive before writing any staged files."""
    with zipfile.ZipFile(archive) as z:
        entries=[]
        for info in z.infolist():
            name=info.filename
            if name.startswith(('/','\\')) or '\\' in name or ':' in name or '..' in PurePosixPath(name).parts:
                raise ValueError('Unsafe archive path.')
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Archive contains a symbolic link.')
            if not info.is_dir():
                entries.append(info)
        prefixes={i.filename[:-len('app.py')] for i in entries
                  if i.filename.endswith('app.py') and i.filename.count('/')<=1}
        prefixes={p for p in prefixes if all(p+r in z.namelist() for r in required)}
        if len(prefixes)!=1:
            raise ValueError('Repository archive does not contain the complete app.')
        prefix=prefixes.pop()
        files={}
        for info in entries:
            if not info.filename.startswith(prefix):
                continue
            name=info.filename[len(prefix):]
            if not safe_name(name):
                raise ValueError('Protected or unsafe path in repository: '+name)
            # Historical build artifacts never participate in source updates.
            if name=='release-manifest.json' or name.lower().endswith(('.zip','.bat','.pyc')):
                continue
            if name in files:
                raise ValueError('Duplicate archive path.')
            files[name]=info
        if not set(required).issubset(files):
            raise ValueError('Missing required source files.')
        for name,info in files.items():
            target=stage/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(z.read(info))
        return list(files)

def update(root=ROOT):
    root=Path(root).resolve()
    cfg=config(root)
    work=Path(tempfile.mkdtemp(prefix='ggf-source-update-'))
    errors=[]
    for index,source in enumerate(cfg['mirrors']):
        try:
            sha=latest(source)
            if sha==installed(root):
                print('Already up to date.',flush=True)
                return sha
            archive=work/f'{index}.zip'
            url=source['archive'].format(revision=sha)
            with urlopen(Request(url,headers={'User-Agent':'GGF-App-Updater'}),timeout=120) as response, archive.open('wb') as output:
                shutil.copyfileobj(response,output)
            stage=work/f'stage-{index}'
            files=stage_archive(archive,stage,cfg['required'])
            break
        except Exception as error:
            errors.append(f"{source['name']}: {error}")
    else:
        raise RuntimeError('No usable repository download. Existing files were kept. '+'; '.join(errors))
    backup=root.parent/'app-backups'/(time.strftime('%Y%m%d-%H%M%S')+'-'+work.name)
    backup.mkdir(parents=True,exist_ok=True)
    existing=[]
    # Complete backups and destination validation precede changes.
    for name in files:
        target=root/name
        if not target.resolve().is_relative_to(root):
            raise ValueError('Destination leaves the app folder: '+name)
        if target.is_file():
            saved=backup/name
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,saved)
            existing.append(name)
        elif target.exists():
            raise ValueError('Source file conflicts with a directory: '+name)
    try:
        for name in files:
            target=root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(stage/name,target)
    except Exception:
        # Restore overwritten source. New files remain harmless until retry.
        for name in existing:
            shutil.copy2(backup/name,root/name)
        raise
    old_marker=root/MARKER
    if old_marker.exists():
        shutil.copy2(old_marker,backup/MARKER)
    old_marker.write_text(json.dumps({'revision':sha,'source':source['name']},indent=2)+'\n')
    print(f"Updated from {source['name']} to {sha}. Backup: {backup}",flush=True)
    return sha

def start_restart(root=ROOT):
    import psutil
    cfg=config(root)
    errors=[]
    for source in cfg['mirrors']:
        try:
            latest(source)
            break
        except Exception as error:
            errors.append(str(error))
    else:
        raise RuntimeError('Update repositories are unavailable. '+'; '.join(errors))
    folder=Path(tempfile.mkdtemp(prefix='ggf-restart-'))
    helper=folder/'update_app.py'
    shutil.copy2(Path(__file__),helper)
    logs=root/'logs'
    logs.mkdir(exist_ok=True)
    command=[sys.executable,str(helper),'--root',str(root),'--restart',
             str(os.getpid()),str(psutil.Process().create_time())]
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with (logs/'update.log').open('a',encoding='utf-8') as stream:
        subprocess.Popen(command,cwd=root,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,creationflags=flags)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--restart',nargs=2)
    args=parser.parse_args()
    root=args.root.resolve()
    if args.check:
        print(check_update(root))
        return
    import psutil
    if args.restart:
        pid,created=int(args.restart[0]),float(args.restart[1])
        deadline=time.monotonic()+45
        while psutil.pid_exists(pid):
            try:
                if psutil.Process(pid).create_time()!=created:
                    break
            except psutil.NoSuchProcess:
                break
            if time.monotonic()>deadline:
                raise RuntimeError('App did not close; update cancelled.')
            time.sleep(.5)
    else:
        lock=root/'app.lock'
        if lock.exists():
            try:
                process=psutil.Process(int(lock.read_text()))
                if any(str(root).lower() in arg.lower() for arg in process.cmdline()):
                    raise RuntimeError('Close the app first or use Update and restart in Settings.')
            except (ValueError,psutil.NoSuchProcess):
                pass
    try:
        before=(root/'requirements.txt').read_bytes()
        update(root)
        if before!=(root/'requirements.txt').read_bytes():
            uv=root/'runtime'/'uv.exe'
            command=([str(uv),'pip','install','--python',sys.executable]
                     if uv.is_file() else [sys.executable,'-m','pip','install'])
            subprocess.run(command+['-r',str(root/'requirements.txt')],check=True)
    finally:
        if args.restart:
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            with (root/'logs'/'restart.log').open('a',encoding='utf-8') as stream:
                subprocess.Popen([sys.executable,str(root/'app.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,creationflags=flags)

if __name__=='__main__':
    main()
