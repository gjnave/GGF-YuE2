"""Install the pinned publisher-built CUDA runtime; never build CUDA on a member's PC."""
import hashlib
from pathlib import Path
import subprocess
import time
import zipfile

ROOT=Path(__file__).resolve().parent
ASSETS=[
 ('audio-v0.8.2-bin-windows-x64-cuda12.4.zip',444938499,'6055122c7199897ff21ca6cda9f9207712bd91273d21dc2d137d5fa610c43c86'),
 ('audio-v0.8.2-cudart-windows-x64-cuda12.4.zip',607273675,'e2a31fb1030423319e686c6ec65da8952b2c095feb8a1e716c2adfbb6c46fac1')]


def verified(path,size,digest):
    if not path.is_file() or path.stat().st_size!=size:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()==digest


def install():
    runtime=ROOT/'runtime'
    downloads=ROOT/'downloads'
    runtime.mkdir(exist_ok=True)
    downloads.mkdir(exist_ok=True)
    required=['audiocpp_cli.exe','ggml-cuda.dll','cublas64_12.dll','model_specs/yue2.json']
    if all((runtime/name).is_file() for name in required) and (runtime/'ready-0.8.2.txt').is_file():
        version=subprocess.run([str(runtime/'audiocpp_cli.exe'),'--version'],capture_output=True,text=True,check=True)
        if 'audio.cpp 0.8.2' in version.stdout:
            print('Native audio.cpp 0.8.2 runtime is ready. Download skipped.')
            return
    for name,size,digest in ASSETS:
        path=downloads/name
        if not verified(path,size,digest):
            if path.exists() and path.stat().st_size>=size:
                path.rename(path.with_name(path.name+f'.invalid-{time.time_ns()}'))
            url=f'https://github.com/0xShug0/audio.cpp/releases/download/v0.8.2/{name}'
            subprocess.run(['curl.exe','--fail','--location','--retry','3','--continue-at','-',
                            '--output',str(path),url],check=True)
            if not verified(path,size,digest):
                raise RuntimeError(f'Checksum failed: {name}. Existing files are preserved; rerun INSTALL.bat.')
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                target=(runtime/info.filename).resolve()
                if not target.is_relative_to(runtime.resolve()) or ':' in info.filename or '\\' in info.filename:
                    raise RuntimeError('Unsafe runtime archive path.')
            archive.extractall(runtime)
    if not all((runtime/name).is_file() for name in required):
        raise RuntimeError('Native runtime extraction was incomplete.')
    subprocess.run([str(runtime/'audiocpp_cli.exe'),'--version'],check=True)
    (runtime/'ready-0.8.2.txt').write_text('Verified official audio.cpp 0.8.2 CUDA 12.4 release archives.\n')


if __name__=='__main__':
    install()
