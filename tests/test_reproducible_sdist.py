import gzip
import hashlib
import io
import pathlib
import tarfile
import tempfile
import unittest

from tools.build_reproducible_sdist import normalize_archive


def make_archive(path, entries, gzip_mtime=0):
    """Write a small gzip tar with caller-controlled member order/metadata."""
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, payload, mtime, kind in entries:
            info = tarfile.TarInfo(name)
            info.mtime = mtime
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                info.size = 0
                archive.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "target"
                archive.addfile(info)
            else:
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
    with path.open("wb") as output:
        with gzip.GzipFile(filename="random-name.tar", mode="wb", fileobj=output, mtime=gzip_mtime) as compressed:
            compressed.write(tar_buffer.getvalue())


class ReproducibleSdistTests(unittest.TestCase):
    def test_normalization_removes_order_and_timestamp_variance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            first = root / "first.tar.gz"
            second = root / "second.tar.gz"
            out_a = root / "a.tar.gz"
            out_b = root / "b.tar.gz"
            entries_a = [
                ("demo-1.0", b"", 1_700_000_001, "dir"),
                ("demo-1.0/alpha.txt", b"alpha", 1_700_000_002, "file"),
                ("demo-1.0/sub", b"", 1_700_000_003, "dir"),
                ("demo-1.0/sub/beta.txt", b"beta", 1_700_000_004, "file"),
            ]
            entries_b = [
                ("demo-1.0/sub/beta.txt", b"beta", 1_600_000_004, "file"),
                ("demo-1.0/sub", b"", 1_600_000_003, "dir"),
                ("demo-1.0/alpha.txt", b"alpha", 1_600_000_002, "file"),
                ("demo-1.0", b"", 1_600_000_001, "dir"),
            ]
            make_archive(first, entries_a, gzip_mtime=1_700_000_000)
            make_archive(second, entries_b, gzip_mtime=1_600_000_000)
            result_a = normalize_archive(first, out_a)
            result_b = normalize_archive(second, out_b)
            self.assertEqual(result_a["sha256"], result_b["sha256"])
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())
            with tarfile.open(out_a, "r:gz") as archive:
                members = archive.getmembers()
                self.assertTrue(all(member.mtime == result_a["mtime"] for member in members))
                self.assertEqual(
                    {member.name for member in members if member.isfile()},
                    {"demo-1.0/alpha.txt", "demo-1.0/sub/beta.txt"},
                )
                self.assertEqual(archive.extractfile("demo-1.0/alpha.txt").read(), b"alpha")

    def test_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source, output = root / "bad.tar.gz", root / "out.tar.gz"
            make_archive(source, [("demo/../escape", b"x", 0, "file")])
            with self.assertRaises(ValueError):
                normalize_archive(source, output)

    def test_rejects_absolute_and_backslash_paths(self):
        for name in ("/absolute", "demo\\escape"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = pathlib.Path(temporary)
                source, output = root / "bad.tar.gz", root / "out.tar.gz"
                make_archive(source, [(name, b"x", 0, "file")])
                with self.assertRaises(ValueError):
                    normalize_archive(source, output)

    def test_rejects_noncanonical_path_aliases(self):
        for name in ("demo//file", "demo/./file", "demo/file/"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = pathlib.Path(temporary)
                source, output = root / "bad.tar.gz", root / "out.tar.gz"
                make_archive(source, [(name, b"x", 0, "file")])
                with self.assertRaises(ValueError):
                    normalize_archive(source, output)

    def test_accepts_standard_trailing_slash_directory_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source, output = root / "input.tar.gz", root / "output.tar.gz"
            make_archive(source, [
                ("demo-1.0/", b"", 123, "dir"),
                ("demo-1.0/file.txt", b"ok", 124, "file"),
            ])
            result = normalize_archive(source, output)
            self.assertEqual(result["members"], 2)
            with tarfile.open(output, "r:gz") as archive:
                self.assertEqual(
                    {member.name for member in archive.getmembers()},
                    {"demo-1.0", "demo-1.0/file.txt"},
                )

    def test_rejects_duplicate_member_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source, output = root / "bad.tar.gz", root / "out.tar.gz"
            make_archive(source, [("demo/a", b"x", 0, "file"), ("demo/a", b"y", 1, "file")])
            with self.assertRaises(ValueError):
                normalize_archive(source, output)

    def test_rejects_symlink_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source, output = root / "bad.tar.gz", root / "out.tar.gz"
            make_archive(source, [("demo/link", b"", 0, "symlink")])
            with self.assertRaises(ValueError):
                normalize_archive(source, output)


if __name__ == "__main__":
    unittest.main()
