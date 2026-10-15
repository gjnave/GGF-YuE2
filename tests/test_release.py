import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import lifecycle
import network_settings
import update_app
import workspace


class ReleaseChecks(unittest.TestCase):
    def test_ui_and_restore(self):
        demo=app.build_demo()
        labels=[c['props'].get('label') for c in demo.config['components'] if c['type']=='tabitem']
        self.assertEqual(labels,['Create','ABC Editor','Settings'])
        restored=app.restore('')
        self.assertEqual(len(restored),19)
        self.assertEqual(restored[3],'full')
        self.assertEqual(len(restored[0]),32)

    def test_blank_and_short_password(self):
        old=network_settings.SETTINGS_PATH
        folder=Path(tempfile.mkdtemp(prefix='yue2-network-test-'))
        network_settings.SETTINGS_PATH=folder/'network.json'
        try:
            saved=network_settings.save_settings('public','ggf','x')
            self.assertTrue(network_settings.verify_login('ggf','x',saved))
            self.assertFalse(network_settings.verify_login('ggf','wrong',saved))
            saved=network_settings.save_settings('public','ggf','')
            self.assertEqual(saved['digest'],'')
            self.assertEqual(saved['salt'],'')
        finally:
            network_settings.SETTINGS_PATH=old

    def test_one_owned_job(self):
        lifecycle.begin('Test')
        try:
            with self.assertRaises(RuntimeError):
                lifecycle.begin('Second job')
            self.assertTrue(lifecycle.snapshot()[0])
        finally:
            lifecycle.finish('Ready')

    def test_archive_protection(self):
        root=Path(tempfile.mkdtemp(prefix='yue2-archive-test-'))
        required=['app.py','requirements.txt']
        good=root/'good.zip'
        with zipfile.ZipFile(good,'w') as archive:
            for name in required:
                archive.writestr('repo/'+name,'test')
        self.assertEqual(set(update_app.stage_archive(good,root/'stage',required)),set(required))
        for name in ['../bad.py','models/weights.bin','network_settings.json','.venv-3.12/anything']:
            bad=root/(str(len(name))+'.zip')
            with zipfile.ZipFile(bad,'w') as archive:
                for needed in required:
                    archive.writestr('repo/'+needed,'test')
                archive.writestr('repo/'+name,'protected')
            with self.assertRaises(ValueError):
                update_app.stage_archive(bad,root/'bad-stage',required)

    def test_abc_roundtrip_without_gpu(self):
        core=app.engine
        text='X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nC D E F | G A B c |\n'
        result=core.save_editor_score_as(text,'release-check.abc')
        path=result[0]
        self.assertEqual(Path(path).read_text(),text)
        opened=core.open_generated_score(path,'','')
        self.assertEqual(opened[0],text)
        with self.assertRaises(Exception):
            core.open_generated_score(path,text+'\n% unsaved',text)
        restored=core.use_editor_score(text,'off')
        self.assertEqual(restored[2]['value'],'full')

    def test_unique_download_name(self):
        import wave
        folder=app.ROOT/'outputs'/'song-release-test'
        folder.mkdir(parents=True,exist_ok=True)
        wav=folder/'audio.wav'
        with wave.open(str(wav),'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(24000)
            stream.writeframes(b'\0\0'*2400)
        audio=app.engine.convert_audio(wav,'flac')
        self.assertTrue(audio.name.startswith('ggf-yue2-song-'))
        self.assertTrue(audio.is_file())


if __name__=='__main__':
    unittest.main()
