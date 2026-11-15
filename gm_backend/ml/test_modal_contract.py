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
