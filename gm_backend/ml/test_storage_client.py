from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from ml.storage_client import (
    generate_presigned_url,
    get_storage_client,
    upload_fileobj,
)


@override_settings(
    R2_ENDPOINT="https://example.r2.cloudflarestorage.com",
    R2_REGION="auto",
    R2_ACCESS_KEY_ID="access-key",
    R2_SECRET_ACCESS_KEY="secret-key",
    R2_DOCUMENTS_BUCKET="musical-bucket",
)
class R2StorageClientTests(SimpleTestCase):
    @patch("ml.storage_client.boto3.client")
    def test_client_uses_r2_configuration(self, boto_client):
        get_storage_client()

        boto_client.assert_called_once_with(
            "s3",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            region_name="auto",
            aws_access_key_id="access-key",
            aws_secret_access_key="secret-key",
        )

    @patch("ml.storage_client.boto3.client")
    def test_upload_uses_configured_bucket(self, boto_client):
        storage = Mock()
        boto_client.return_value = storage
        file_obj = Mock(name="audio.wav")
        file_obj.name = "audio.wav"

        key = upload_fileobj(file_obj, folder="stems/uploads")

        self.assertTrue(key.startswith("stems/uploads/"))
        self.assertTrue(key.endswith(".wav"))
        storage.upload_fileobj.assert_called_once()
        self.assertEqual(storage.upload_fileobj.call_args.args[1], "musical-bucket")

    @patch("ml.storage_client.boto3.client")
    def test_presigned_url_uses_get_object(self, boto_client):
        storage = Mock()
        storage.generate_presigned_url.return_value = "https://signed.example/audio.wav"
        boto_client.return_value = storage

        result = generate_presigned_url("songs/audio.wav", expiry_seconds=600)

        self.assertEqual(result, "https://signed.example/audio.wav")
        storage.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "musical-bucket", "Key": "songs/audio.wav"},
            ExpiresIn=600,
        )
