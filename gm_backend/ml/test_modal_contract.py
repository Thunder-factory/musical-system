from pathlib import Path
from unittest import TestCase


class ModalDemucsContractTests(TestCase):
    def setUp(self):
        root = Path(__file__).parent
        self.music_source = (root / 'modal_music_server.py').read_text()
        self.demucs_source = (root / 'modal_demucs_server.py').read_text()

    def test_music_image_does_not_install_demucs(self):
        self.assertNotIn('demucs>=', self.music_source)
        self.assertNotIn('process_stems_job', self.music_source)

    def test_demucs_contract_has_sync_async_and_status_paths(self):
        self.assertIn('client_job_id', self.demucs_source)
        self.assertIn('remote_job_id', self.demucs_source)
        self.assertIn('action") == "status"', self.demucs_source)
        self.assertIn('vocals', self.demucs_source)
        self.assertIn('no_vocals', self.demucs_source)

    def test_demucs_is_protected_and_uses_shared_app(self):
        self.assertIn('requires_proxy_auth=True', self.demucs_source)
        self.assertIn('from .modal_app import app', self.demucs_source)
        self.assertIn('timeout=1800', self.demucs_source)
        self.assertIn('DEMUCS_SPAWN_LEASE_SECONDS', self.demucs_source)


class ModalFaceSwapContractTests(TestCase):
    def setUp(self):
        root = Path(__file__).parent
        self.music_source = (root / 'modal_music_server.py').read_text()
        self.faceswap_source = (root / 'modal_faceswap_server.py').read_text()

    def test_faceswap_is_protected_async_and_uses_shared_app(self):
        for token in (
            'requires_proxy_auth=True',
            'from .modal_app import app',
            'action") == "status"',
            'client_job_id',
            'output_s3_key',
            'music-gen-secret',
            'FACESWAP_SPAWN_LEASE_SECONDS',
        ):
            self.assertIn(token, self.faceswap_source)

    def test_faceswap_has_no_watermark_nor_data_volume(self):
        self.assertNotIn('drawtext', self.faceswap_source)
        self.assertNotIn('faceswap-data', self.faceswap_source)

    def test_music_server_imports_faceswap_without_installing_it(self):
        self.assertIn('modal_faceswap_server', self.music_source)
        self.assertNotIn('facefusion', self.music_source)
        self.assertNotIn('onnxruntime', self.music_source)

    def test_every_music_image_ships_the_modules_imported_at_startup(self):
        # Cada contenedor de gm-music-server vuelve a importar modal_music_server.py, que
        # importa estos módulos locales: si una imagen no los incluye, el contenedor falla al
        # arrancar y Modal lo reinicia en bucle (pasó con CoverServer al unir faceswap).
        import re

        required = ('modal_demucs_server', 'modal_faceswap_server', 'prompts')
        calls = re.findall(r'add_local_python_source\(([^)]*)\)', self.music_source)
        self.assertGreaterEqual(len(calls), 3)
        for call in calls:
            for module in required:
                self.assertIn(f'"{module}"', call, f'falta {module} en add_local_python_source({call})')

    def test_demucs_image_can_write_wav(self):
        demucs_source = (Path(__file__).parent / 'modal_demucs_server.py').read_text()
        self.assertIn('soundfile', demucs_source)
