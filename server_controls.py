"""Phone-accessible controls for this app's models and local/remote servers."""
import atexit
import os
import threading

_SERVERS = []
_STOPPING = threading.Event()


def ensure_running():
    if _STOPPING.is_set():
        raise RuntimeError('The app is shutting down. Restart it on the local PC to generate again.')


def register_servers(*servers):
    _SERVERS.extend(server for server in servers if server is not None)


def _exit_server():
    try:
        for server in _SERVERS:
            try:
                server.close(verbose=False)
            except Exception:
                pass
        # Includes Gradio's owned public-link tunnel cleanup.
        atexit._run_exitfuncs()
    finally:
        os._exit(0)


class ServerControls:
    def __init__(self, locks, release):
        self.locks = locks
        self.release = release
        self.stopping = False
        self.guard = threading.Lock()

    def _acquire(self):
        acquired = []
        for lock in self.locks():
            if not lock.acquire(blocking=False):
                for previous in reversed(acquired):
                    previous.release()
                return None
            acquired.append(lock)
        return acquired

    def perform(self, shutdown=False):
        with self.guard:
            if self.stopping:
                return 'The app is shutting down. Restart it on the local PC to use it again.'
            acquired = self._acquire()
            if acquired is None:
                return 'Generation is running. Let it finish or stop the generation first, then try again.'
            try:
                self.release()
                if not shutdown:
                    return ('YuE2 releases its native engine and GPU memory after every song. '
                            'No model is held open while idle. The app and phone link stay open.')
                self.stopping = True
                _STOPPING.set()
                timer = threading.Timer(3, _exit_server)
                timer.daemon = True
                timer.start()
                return 'Shutting down the app and its server. Restart the app on the local PC to use it again.'
            finally:
                for lock in reversed(acquired):
                    lock.release()


def add_server_controls(controls):
    import gradio as gr
    gr.Markdown('### App and GPU memory')
    gr.Markdown('The native engine unloads automatically after each song. Saved music and installed models stay on disk.')
    with gr.Row():
        release = gr.Button('Release models / free GPU memory', variant='secondary')
        stop = gr.Button('Stop server', variant='secondary')
    status = gr.Markdown('')
    with gr.Column(visible=False) as confirmation:
        gr.Markdown('**Shut down this app?** This closes the app, its server and your phone connection. '
                    'You must restart it on the local PC. To keep the app running, choose '
                    '**Release models / free GPU memory** instead; models reload on your next generation.')
        with gr.Row():
            confirm = gr.Button('Yes, shut down app', variant='stop')
            cancel = gr.Button('Keep app running', variant='secondary')
    release.click(controls.perform, outputs=status, queue=False, api_name=False)
    stop.click(lambda: gr.update(visible=True), outputs=confirmation, queue=False, api_name=False)
    cancel.click(lambda: gr.update(visible=False), outputs=confirmation, queue=False, api_name=False)
    confirm.click(lambda: (controls.perform(shutdown=True), gr.update(visible=False)),
                  outputs=[status, confirmation], queue=False, api_name=False)
    return status
