import unittest
from prepare_release import manifest


class ReleasePreparationTest(unittest.TestCase):
    def setUp(self):
        self.metadata = {"package": "org.sevamrita.mobile", "version_code": 20,
                         "version_name": "0.5.0", "min_sdk": 26, "debuggable": False}

    def make(self, metadata=None, key="known"):
        return manifest(metadata or self.metadata, key, "known", b"APK", "org.sevamrita.mobile", "Release notes")

    def test_production_feed_has_versioned_immutable_apk_and_digest(self):
        data = self.make()
        self.assertEqual(data["size_bytes"], 3)
        self.assertEqual(len(data["sha256"]), 64)
        self.assertTrue(data["apk_url"].endswith("/sf-tasks-v0.5.0/SF-Tasks-0.5.0.apk"))

    def test_wrong_signer_debug_build_and_channel_mix_are_rejected(self):
        for changes in ({"debuggable": True}, {"package": "org.sevamrita.mobile.local"},
                        {"version_code": 0}, {"version_name": "0.5.0-local"}):
            with self.assertRaises(ValueError):
                self.make(self.metadata | changes)
        with self.assertRaises(ValueError):
            self.make(key="unknown")

    def test_testing_feed_never_points_to_production_package(self):
        metadata = self.metadata | {"package": "org.sevamrita.mobile.local", "version_name": "0.5.0-local", "debuggable": True}
        data = manifest(metadata, "debug-key", "debug-key", b"APK", "org.sevamrita.mobile.local", "Test notes")
        self.assertTrue(data["apk_url"].endswith("/SF-testing-0.5.0.apk"))
        self.assertEqual(data["package_name"], "org.sevamrita.mobile.local")


if __name__ == "__main__":
    unittest.main()
