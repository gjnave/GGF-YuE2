"""GGF YuE2 Music Studio: native GGUF inference, desktop and optional phone UI."""
from pathlib import Path
import argparse
import base64
import json
import os
import sys
import threading
import time

import gradio as gr
import lifecycle as jobs
import yue2_gguf_gui as engine
import workspace
import network_settings as network
from server_controls import ServerControls, add_server_controls, ensure_running, register_servers
import update_app

ROOT=Path(__file__).resolve().parent
VERSION='2026.10.15'
MODES=[('This PC only','local'),('Local network / Wi-Fi','lan'),('Temporary public phone link','public')]


def guarded(function,*args):
    ensure_running()
    jobs.begin('Preparing…')
    try:
        result=function(*args)
        jobs.finish('Finished. Ready for the next song.')
        return result
    except Exception as error:
        jobs.finish('Stopped.' if jobs.CANCEL.is_set() else f'Error: {error}')
        raise gr.Error(str(error)) from None


def generate(key,*values):
    ensure_running()
    jobs.begin('Checking model and preparing song…')
    started=time.monotonic()
    try:
        style,lyrics,cot,seed,quant,fmt,save_abc,instrumental,strength,abc=values
        if abc:
            engine.validate_abc(Path(abc).read_text(encoding='utf-8-sig'))
            abc=workspace.retain_abc(key,abc)
        workspace.save(key,values[:9])
        result=engine.generate(style,lyrics,cot,seed,abc,quant,fmt,save_abc,instrumental,strength)
        workspace.save(key,result=result[0],score=result[-1])
        jobs.finish(f'**Song complete · {time.monotonic()-started:.1f} seconds.** Saved in outputs. GPU memory released.')
        return result
    except Exception as error:
        # A wrapper failure must not leave an app-owned native process consuming GPU memory.
        if jobs.PROCESS is not None and jobs.PROCESS.poll() is None:
            jobs.stop()
            jobs.PROCESS.wait(timeout=15)
        jobs.finish('Generation stopped. Saved songs are kept.' if jobs.CANCEL.is_set() else f'**Generation failed:** {error}')
        raise gr.Error(str(error)) from None


def restore(key):
    key=workspace.token(key)
    data=workspace.read(key)
    defaults=[*engine.load_last_prompt(),'full',engine.SESSION_SEED,'q8','flac',False,False,1.0]
    values=[data.get(name,default) for name,default in zip(workspace.KEYS,defaults)]
    values[2]=values[2] if values[2] in ('full','melody','off') else 'full'
    values[4]=values[4] if values[4] in ('q8','q4') else 'q8'
    values[5]=values[5] if values[5] in ('flac','mp3') else 'flac'
    song=workspace.owned(data.get('result'))
    score=workspace.owned(data.get('score'))
    editor_path=workspace.owned(data.get('editor_path'))
    return (key,*values,workspace.owned(data.get('abc')),song,song,
            gr.update(value=score,visible=bool(score)),score,gr.update(visible=bool(score)),
            data.get('editor_text',''),editor_path,data.get('editor_baseline',''))


def theme():
    return gr.themes.Base(primary_hue='amber',secondary_hue='slate',neutral_hue='slate').set(
        body_background_fill='#07101f',body_background_fill_dark='#07101f',
        body_text_color='#e8eef9',body_text_color_dark='#e8eef9',
        block_background_fill='#111c2f',block_background_fill_dark='#111c2f',
        block_label_text_color='#e8eef9',block_label_text_color_dark='#e8eef9',
        block_title_text_color='#e8eef9',block_title_text_color_dark='#e8eef9',
        input_background_fill='#091425',input_background_fill_dark='#091425',
        input_border_color='#435570',input_border_color_dark='#435570',
        input_placeholder_color='#9baec8',input_placeholder_color_dark='#9baec8',
        button_primary_background_fill='#f5b942',button_primary_background_fill_dark='#f5b942',
        button_primary_text_color='#091425',button_primary_text_color_dark='#091425')


def build_demo():
    settings=network.read_settings()
    logo=base64.b64encode((ROOT/'assets'/'ggf-brain-logo.png').read_bytes()).decode()
    with gr.Blocks(title='GGF YuE2 Music Studio') as demo:
        gr.HTML(f'<header id="hero"><div><span class="eyebrow">GET GOING FAST · LOCAL AI</span><h1>YuE2 Music Studio</h1><p>Your words. Your sound. Your song.</p><nav><a href="https://getgoingfast.pro" target="_blank" rel="noopener">GetGoingFast.pro ↗</a><a href="https://youtube.com/@TheAIHobbyGuy" target="_blank" rel="noopener">The AI Hobby Guy ↗</a></nav></div><img src="data:image/png;base64,{logo}" alt="GGF"></header>')
        activity=gr.Markdown('Ready to create music.',elem_id='activity')
        key=gr.State('')
        with gr.Tabs(selected='generate') as tabs:
            with gr.Tab('Create',id='generate'):
                gr.Markdown('Describe the music, add lyrics, then generate. For music without vocals, open **Instrumental** below.')
                with gr.Row(equal_height=False,elem_id='create-row'):
                    with gr.Column(min_width=280):
                        style=gr.Textbox(label='Style and sound',lines=3)
                        lyrics=gr.Textbox(label='Lyrics',lines=10)
                        with gr.Accordion('Instrumental',open=False):
                            instrumental=gr.Checkbox(label='Use instrumental LoRA',value=False)
                            strength=gr.Slider(0,1.5,value=1,step=.05,label='LoRA strength')
                            gr.Markdown('Use Full plan and `[instrumental]` or section tags instead of lyrics. Install the optional 140 MB adapter in Settings.')
                            template=gr.Button('Use instrumental template')
                        with gr.Accordion('Song options',open=False):
                            cot=gr.Dropdown([('Full plan','full'),('Melody plan','melody'),('Direct generation','off')],value='full',label='Musical plan')
                            with gr.Row():
                                seed=gr.Number(value=engine.SESSION_SEED,precision=0,minimum=0,label='Seed')
                                randomize=gr.Button('Randomize seed')
                            quant=gr.Dropdown([('Q8 · higher fidelity','q8'),('Q4 · lower VRAM','q4')],value='q8',label='Model')
                            fmt=gr.Dropdown([('FLAC · lossless','flac'),('MP3 · 320 kbps','mp3')],value='flac',label='Download format')
                            save_abc=gr.Checkbox(label='Save generated ABC score',value=False)
                            gr.Markdown('Direct generation skips musical planning; it cannot import or export an ABC score. This app does not impose a song-duration cap.')
                        with gr.Accordion('Existing ABC score (optional)',open=False) as abc_accordion:
                            abc=gr.File(label='ABC score',type='filepath',file_types=['.abc'])
                        start=gr.Button('Generate song',variant='primary')
                        stop=gr.Button('Stop generation',variant='stop')
                    with gr.Column(min_width=280):
                        audio=gr.Audio(label='Your song',type='filepath')
                        current_song=gr.State(None)
                        with gr.Accordion('Download another format',open=False):
                            convert_format=gr.Dropdown([('FLAC · lossless','flac'),('MP3 · 320 kbps','mp3')],value='mp3',label='Format')
                            convert=gr.Button('Convert saved song')
                            convert_status=gr.Markdown('',visible=False)
                        score=gr.File(label='ABC score',visible=False)
                        latest_score=gr.State(None)
                        edit_abc=gr.Button('Edit ABC',visible=False)
                        location=gr.Textbox(label='Saved files',lines=3,interactive=False,visible=False)
                        gr.Markdown('[Put your music to video with GrizzlyMax ↗](https://getgoingfast.pro/tools/grizzlymax/)')
            with gr.Tab('ABC Editor',id='editor') as editor_tab:
                gr.Markdown('Edit a generated score or open an `.abc` file. **Use This Score** sends your current edits to Create.')
                editor_path=gr.State(None)
                baseline=gr.State('')
                uploaded=gr.File(label='Open ABC score',type='filepath',file_types=['.abc'])
                recent=gr.Button('Open most recent generated score')
                editor_text=gr.Textbox(label='ABC score',lines=22,elem_id='score-editor')
                editor_status=gr.Markdown('Open or generate a score to begin.')
                with gr.Row():
                    save=gr.Button('Save')
                    save_name=gr.Textbox(label='Save As filename',value='edited-score.abc')
                    save_as=gr.Button('Save As')
                editor_download=gr.File(label='Download ABC score',visible=False)
                use_score=gr.Button('Use This Score',variant='primary')
            with gr.Tab('Settings',id='settings'):
                gr.Markdown('### Use it from your phone\nYour PC runs the model; your phone controls the app. Choose an access mode and save, then restart the app. The local PC page always stays login-free.')
                mode=gr.Dropdown(MODES,value=settings['mode'],label='Access mode')
                username=gr.Textbox(value=settings['username'],label='Remote username (optional)')
                password=gr.Textbox(type='password',label='New remote password (optional)',info='Saving a blank password turns remote login off. Public links are temporary and may change on restart.')
                save_network=gr.Button('Save phone access')
                network_status=gr.Markdown('')
                gr.Markdown('### Installed models\nQ8 is the fidelity default. Q4 reduces memory use. Downloads are resumed and SHA-256 verified; existing verified files are kept.')
                download=gr.Button('Download / repair selected model')
                download_lora=gr.Button('Download instrumental LoRA (140 MB)')
                model_status=gr.Markdown('')
                gr.Markdown('### Updates')
                with gr.Row():
                    check=gr.Button('Check for updates')
                    update=gr.Button('Update and restart')
                update_status=gr.Markdown('Updates not checked yet.')
                controls=ServerControls(lambda:[jobs.LOCK],lambda:None)
                add_server_controls(controls)
                gr.Markdown('YuE2 model weights and the optional instrumental LoRA are licensed CC BY-NC 4.0. Review the upstream terms before use.')
        gr.HTML(f'<div id="powered">GGF · Build {VERSION} · Powered by YuE2 / audio.cpp · Music is saved in the app’s outputs folder</div>')
        values=[style,lyrics,cot,seed,quant,fmt,save_abc,instrumental,strength]
        restore_outputs=[key,*values,abc,audio,current_song,score,latest_score,edit_abc,editor_text,editor_path,baseline]
        demo.load(restore,inputs=key,outputs=restore_outputs,js="(k)=>{let v=localStorage.getItem('ggf-yue2-workspace');if(!/^[a-f0-9]{32}$/.test(v||'')){v=crypto.randomUUID().replaceAll('-','');localStorage.setItem('ggf-yue2-workspace',v)}return v}")
        for control in values:
            control.change(lambda k,*v:workspace.save(k,v),inputs=[key,*values],outputs=None,trigger_mode='always_last',api_name=False)
        abc.upload(lambda k,p:workspace.retain_abc(k,p),inputs=[key,abc],outputs=abc,api_name=False)
        abc.clear(lambda k:workspace.save(k,abc=None),inputs=key,api_name=False)
        editor_text.change(lambda k,t,p,b:workspace.save(k,editor_text=t,editor_path=p,editor_baseline=b),inputs=[key,editor_text,editor_path,baseline],api_name=False)
        start.click(lambda:(None,None,gr.update(visible=False)),outputs=[audio,current_song,location],queue=False,api_name=False).then(
            generate,inputs=[key,*values,abc],outputs=[audio,score,location,current_song,convert_status,edit_abc,latest_score],concurrency_limit=None,api_name=False)
        stop.click(jobs.stop,outputs=activity,queue=False,api_name=False)
        gr.Timer(1).tick(lambda:(jobs.snapshot()[1],gr.update(interactive=not jobs.snapshot()[0])),outputs=[activity,start],queue=False,api_name=False)
        template.click(engine.instrumental_template,outputs=[lyrics,cot,save_abc],api_name=False)
        randomize.click(engine.random_seed,outputs=seed,api_name=False)
        convert.click(lambda p,f:guarded(engine.convert_current_song,p,f),inputs=[current_song,convert_format],outputs=[audio,convert_status],api_name=False)
        editor_outputs=[editor_text,editor_path,baseline,editor_status,editor_download]
        editor_tab.select(engine.auto_open_recent_score,inputs=[editor_path,editor_text,baseline],outputs=editor_outputs,api_name=False)
        uploaded.upload(engine.open_uploaded_score,inputs=[uploaded,editor_text,baseline],outputs=editor_outputs,api_name=False)
        recent.click(engine.open_recent_score,inputs=[editor_text,baseline],outputs=editor_outputs,api_name=False)
        edit_abc.click(engine.edit_generated_in_editor,inputs=[latest_score,editor_text,baseline],outputs=[*editor_outputs,tabs],api_name=False)
        save.click(engine.save_editor_score,inputs=[editor_text,editor_path],outputs=[editor_path,baseline,editor_status,editor_download],api_name=False)
        save_as.click(engine.save_editor_score_as,inputs=[editor_text,save_name],outputs=[editor_path,baseline,editor_status,editor_download],api_name=False)
        use_score.click(engine.use_editor_score,inputs=[editor_text,cot],outputs=[abc,tabs,cot,save_abc,abc_accordion,editor_status],api_name=False)
        def save_access(m,u,p):
            network.save_settings(m,u,p)
            return 'Saved. Restart the app to apply phone access. Local PC access remains login-free.'
        save_network.click(save_access,inputs=[mode,username,password],outputs=network_status,api_name=False)
        download.click(lambda q:guarded(engine.download_model,q),inputs=quant,outputs=model_status,api_name=False)
        download_lora.click(lambda:guarded(engine.download_lora),outputs=model_status,api_name=False)
        check.click(update_app.check_update,outputs=update_status,api_name=False)
        def restart_update():
            ensure_running()
            if not jobs.LOCK.acquire(blocking=False):
                return 'Stop generation or wait for it to finish before updating.'
            try:
                update_app.start_restart()
                # Do not accept another job while the updater waits for our exit.
                controls.stopping=True
                from server_controls import _STOPPING,_exit_server
                _STOPPING.set()
                threading.Timer(3,_exit_server).start()
                return 'Updating and restarting. Reopen the local page; a public phone link may change.'
            finally:
                jobs.LOCK.release()
        update.click(restart_update,outputs=update_status,queue=False,api_name=False)
    return demo.queue(default_concurrency_limit=1,max_size=8)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--public',action='store_true',help='Temporary development override; settings are unchanged.')
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    lock=ROOT/'app.lock'
    if lock.is_file():
        import psutil
        try:
            previous=psutil.Process(int(lock.read_text()))
            if previous.pid != os.getpid() and any(str(ROOT).lower() in part.lower() for part in previous.cmdline()):
                raise SystemExit('YuE2 is already running. Open http://127.0.0.1:7871 or use its printed local URL.')
        except (ValueError,psutil.NoSuchProcess,psutil.AccessDenied):
            pass
    ROOT.joinpath('outputs').mkdir(exist_ok=True)
    ROOT.joinpath('app.lock').write_text(str(os.getpid()))
    network.install_upload_disconnect_handling()
    settings=network.read_settings()
    mode='public' if args.public else settings['mode']
    auth=(lambda u,p:network.verify_login(u,p,settings)) if settings['digest'] else None
    local,remote,_,_=network.launch_access_servers(build_demo,mode=mode,preferred_port=7871,auth=auth,
        inbrowser=not args.no_browser,show_error=True,theme=theme(),css=(ROOT/'ui.css').read_text(),
        allowed_paths=[str(ROOT/'outputs'),str(workspace.WORK)])
    register_servers(local,remote)
    threading.Event().wait()


if __name__=='__main__':
    main()
