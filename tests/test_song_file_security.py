#!/usr/bin/env python3

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append("./")
sys.path.append("../")

from lib.song_file_security import SongFileError, bundle_member_paths, resolve_song_path, validate_song_filename


class TestSongFileSecurity(unittest.TestCase):
    def test_rejects_path_traversal_and_absolute_song_names(self):
        for candidate in ("../secret.mid", "..\\secret.mid", "/tmp/secret.mid", "C:\\tmp\\secret.mid"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(SongFileError):
                    validate_song_filename(candidate)

    def test_rejects_unsupported_song_extension(self):
        with self.assertRaises(SongFileError):
            validate_song_filename("payload.py")

    def test_resolves_valid_song_inside_songs_directory(self):
        resolved = resolve_song_path("Ludwig van Beethoven - Fur Elise.mid")

        self.assertEqual(resolved.name, "Ludwig van Beethoven - Fur Elise.mid")
        self.assertEqual(resolved.parent.name, "Songs")

    def test_bundle_members_only_match_expected_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            songs = Path(tmp)
            expected = songs / "Suite_main.mid"
            expected.write_text("", encoding="utf-8")
            (songs / "Suite_left.mid").write_text("", encoding="utf-8")
            (songs / "OtherSuite_main.mid").write_text("", encoding="utf-8")
            (songs / "Suite.zip").write_text("", encoding="utf-8")
            (songs / "Suiteevil.mid").write_text("", encoding="utf-8")

            members = [path.name for path in bundle_member_paths("Suite_main.mid", base_dir=songs)]

        self.assertEqual(members, ["Suite_left.mid", "Suite_main.mid"])


if __name__ == "__main__":
    unittest.main()
