"""Unit checks for server-side avatar validation, upload and cleanup."""

import io
import unittest
from types import SimpleNamespace
from unittest import mock

from backend.__main__ import app
from backend.src.routes import account

USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_ID = "00000000-0000-0000-0000-000000000002"
PROJECT = "https://project.supabase.co"
OLD_PATH = f"{USER_ID}/old-avatar.png"
OLD_URL = f"{PROJECT}/storage/v1/object/public/avatars/{OLD_PATH}"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF = b"GIF89a" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8


class AvatarValidationTests(unittest.TestCase):
    def setUp(self):
        self.patch = mock.patch.object(account, "SUPABASE_URL", PROJECT)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_accepts_allowed_image_signatures(self):
        cases = (
            ("avatar.png", "image/png", PNG, "png"),
            ("avatar.jpg", "image/jpeg", JPEG, "jpg"),
            ("avatar.jpeg", "image/jpeg", JPEG, "jpg"),
            ("avatar.gif", "image/gif", GIF, "gif"),
            ("avatar.webp", "image/webp", WEBP, "webp"),
        )
        for name, mime, data, ext in cases:
            with self.subTest(name=name):
                self.assertEqual(
                    account._validate_avatar(name, mime, data),
                    (mime, ext),
                )

    def test_rejects_extension_mime_or_magic_mismatch(self):
        for name, mime, data in (
            ("avatar.png", "image/jpeg", PNG),
            ("avatar.txt", "image/png", PNG),
            ("avatar.png", "image/png", b"<script>alert(1)</script>"),
            ("avatar.svg", "image/svg+xml", b"<svg/>"),
        ):
            with self.subTest(name=name, mime=mime):
                with self.assertRaises(account.AvatarValidationError):
                    account._validate_avatar(name, mime, data)

    def test_rejects_empty_and_oversize_files(self):
        with self.assertRaises(account.AvatarValidationError):
            account._validate_avatar("avatar.png", "image/png", b"")
        oversize = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024)
        with self.assertRaises(account.AvatarTooLarge):
            account._validate_avatar("avatar.png", "image/png", oversize)

    def test_only_public_avatar_urls_in_the_users_own_folder_are_owned(self):
        self.assertEqual(
            account._owned_avatar_path(OLD_URL, USER_ID),
            OLD_PATH,
        )
        for url in (
            None,
            "",
            "https://example.com/avatar.png",
            f"{PROJECT}/storage/v1/object/public/avatars/{OTHER_ID}/x.png",
            f"{PROJECT}/storage/v1/object/public/avatars/{USER_ID}/../x.png",
            f"{PROJECT}/storage/v1/object/public/other/{USER_ID}/x.png",
            f"https://evil.example/storage/v1/object/public/avatars/{OLD_PATH}",
        ):
            with self.subTest(url=url):
                self.assertIsNone(account._owned_avatar_path(url, USER_ID))


class FakeProfileTable:
    def __init__(self, row, fail_update=False):
        self.row = dict(row)
        self.fail_update = fail_update
        self.values = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def update(self, values):
        self.values = dict(values)
        return self

    def execute(self):
        if self.values is not None:
            if self.fail_update:
                raise RuntimeError("database unavailable")
            self.row.update(self.values)
        return SimpleNamespace(data=[dict(self.row)])


class FakeClient:
    def __init__(self, row, fail_update=False):
        self.table_obj = FakeProfileTable(row, fail_update=fail_update)

    def table(self, _name):
        return self.table_obj


class AvatarEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.profile = {"id": USER_ID, "avatar_url": OLD_URL}
        self.fake = FakeClient(self.profile)
        self.patches = [
            mock.patch.object(account, "SUPABASE_URL", PROJECT),
            mock.patch.object(account, "PUBLISHABLE_KEY", "publishable"),
            mock.patch.object(account, "SECRET_KEY", "service-secret"),
            mock.patch.object(
                account,
                "_user_client",
                return_value=self.fake,
            ),
            mock.patch(
                "backend.src.flask_auth.verify_access_token",
                return_value={"sub": USER_ID, "role": "authenticated"},
            ),
            mock.patch.object(
                account,
                "_configure_avatar_bucket",
                return_value=(True, None),
            ),
            mock.patch.object(
                account,
                "_account_payload",
                side_effect=lambda client: {
                    "user_id": USER_ID,
                    "profile": client.table_obj.row,
                },
            ),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()

    def post(self, data, name="avatar.png", mime="image/png"):
        return self.client.post(
            "/api/account/avatar",
            headers={"Authorization": "Bearer test-token"},
            data={"file": (io.BytesIO(data), name, mime)},
            content_type="multipart/form-data",
        )

    def test_upload_updates_profile_before_deleting_old_avatar(self):
        new_path = f"{USER_ID}/new-avatar.png"
        new_url = f"{PROJECT}/storage/v1/object/public/avatars/{new_path}"
        with mock.patch.object(
            account, "_upload_avatar_object", return_value=(new_path, new_url)
        ) as upload, mock.patch.object(
            account, "_delete_owned_avatar", return_value=True
        ) as delete:
            res = self.post(PNG)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["profile"]["avatar_url"], new_url)
        upload.assert_called_once()
        delete.assert_called_once_with(OLD_URL, USER_ID)
        self.assertEqual(self.fake.table_obj.row["avatar_url"], new_url)

    def test_new_avatar_is_not_deleted_when_profile_update_fails(self):
        self.fake = FakeClient(self.profile, fail_update=True)
        with mock.patch.object(
            account, "_user_client", return_value=self.fake
        ), mock.patch.object(
            account,
            "_upload_avatar_object",
            return_value=(
                f"{USER_ID}/new-avatar.png",
                f"{PROJECT}/storage/v1/object/public/avatars/{USER_ID}/new-avatar.png",
            ),
        ) as upload, mock.patch.object(
            account, "_delete_owned_avatar"
        ) as delete:
            res = self.post(PNG)

        self.assertEqual(res.status_code, 502)
        upload.assert_called_once()
        delete.assert_not_called()

    def test_cleanup_failure_does_not_fail_avatar_update(self):
        new_url = f"{PROJECT}/storage/v1/object/public/avatars/{USER_ID}/new.png"
        with mock.patch.object(
            account, "_upload_avatar_object", return_value=(f"{USER_ID}/new.png", new_url)
        ), mock.patch.object(
            account, "_delete_owned_avatar", return_value=False
        ):
            res = self.post(PNG)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["profile"]["avatar_url"], new_url)

    def test_invalid_file_is_rejected_before_upload(self):
        with mock.patch.object(account, "_upload_avatar_object") as upload:
            res = self.post(b"<script>alert(1)</script>", name="avatar.png")
        self.assertEqual(res.status_code, 400)
        upload.assert_not_called()

    def test_missing_file_is_400(self):
        res = self.client.post(
            "/api/account/avatar",
            headers={"Authorization": "Bearer test-token"},
            data={},
            content_type="multipart/form-data",
        )
        self.assertEqual(res.status_code, 400)

    def test_missing_service_key_is_503(self):
        with mock.patch.object(account, "SECRET_KEY", ""):
            res = self.post(PNG)
        self.assertEqual(res.status_code, 503)

    def test_upload_object_uses_service_key_and_user_folder(self):
        response = mock.Mock(status_code=200, text="")
        with mock.patch.object(account.httpx, "post", return_value=response) as post:
            path, url = account._upload_avatar_object(USER_ID, PNG, "image/png", "png")

        self.assertTrue(path.startswith(f"{USER_ID}/"))
        self.assertTrue(path.endswith(".png"))
        self.assertEqual(
            url,
            f"{PROJECT}/storage/v1/object/public/avatars/{path}",
        )
        args, kwargs = post.call_args
        self.assertTrue(args[0].endswith(f"/storage/v1/object/avatars/{path}"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer service-secret")
        self.assertEqual(kwargs["headers"]["Content-Type"], "image/png")
        self.assertEqual(kwargs["content"], PNG)

    def test_delete_owned_avatar_uses_service_key(self):
        response = mock.Mock(status_code=200, text="")
        with app.app_context(), mock.patch.object(
            account.httpx, "request", return_value=response
        ) as request:
            self.assertTrue(account._delete_owned_avatar(OLD_URL, USER_ID))

        args, kwargs = request.call_args
        self.assertEqual(args[0], "DELETE")
        self.assertTrue(args[1].endswith(f"/storage/v1/object/avatars/{OLD_PATH}"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer service-secret")

    def test_delete_owned_avatar_skips_external_or_other_user_urls(self):
        with app.app_context(), mock.patch.object(account.httpx, "request") as request:
            self.assertFalse(
                account._delete_owned_avatar("https://example.com/x.png", USER_ID)
            )
            self.assertFalse(
                account._delete_owned_avatar(
                    f"{PROJECT}/storage/v1/object/public/avatars/{OTHER_ID}/x.png",
                    USER_ID,
                )
            )
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
