"""One owned native job across the local and phone interfaces."""
import threading
import time

LOCK = threading.Lock()
GUARD = threading.Lock()
CANCEL = threading.Event()
PROCESS = None
STATUS = {'busy': False, 'message': 'Ready to create music.', 'started': 0}


def begin(message):
    if not LOCK.acquire(blocking=False):
        raise RuntimeError('This app is already working. Wait for it to finish or press Stop generation.')
    CANCEL.clear()
    with GUARD:
        STATUS.update(busy=True, message=message, started=time.monotonic())


def stage(message):
    with GUARD:
        STATUS['message'] = str(message)[-350:]


def finish(message):
    global PROCESS
    with GUARD:
        PROCESS = None
        STATUS.update(busy=False, message=message)
    LOCK.release()


def register(process):
    global PROCESS
    with GUARD:
        PROCESS = process
    if CANCEL.is_set():
        stop()


def stop():
    import psutil
    with GUARD:
        process = PROCESS
        busy = STATUS['busy']
    if not busy:
        return 'No generation is running.'
    if process is None:
        return 'Preparing the job. Stop will take effect before the native engine starts.' if CANCEL.is_set() else _cancel_pending()
    CANCEL.set()
    try:
        parent = psutil.Process(process.pid)
        if process.poll() is None:
            children = parent.children(recursive=True)
            for child in reversed(children):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
    except psutil.NoSuchProcess:
        pass
    stage('Stopping generation…')
    return 'Stopping generation. Saved songs are kept.'


def _cancel_pending():
    CANCEL.set()
    return 'Stop requested. Waiting for preparation to finish.'


def snapshot():
    with GUARD:
        value = STATUS.copy()
    if value['busy']:
        elapsed = int(time.monotonic() - value['started'])
        return True, f"**WORKING · {elapsed // 60}:{elapsed % 60:02d}** — {value['message']}"
    return False, value['message']
