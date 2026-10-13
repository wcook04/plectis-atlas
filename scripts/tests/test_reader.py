#!/usr/bin/env python3
"""Checks for the site's door to Statement Map's packets (scripts/reader.py).

    python3 scripts/tests/test_reader.py

The vendored export must load and every packet must pass its checks. A page
must never be built from a packet that was altered, removed, or taken from
another generation, so each of those cases has to stop the build. A number
whose state is unavailable must never come back as zero. Standard library only.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reader as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class VendoredExport(unittest.TestCase):
    def test_every_packet_passes(self):
        r = R.Reader()
        self.assertGreater(r.verify_all(), 1000)

    def test_specimen_families_resolve(self):
        r = R.Reader()
        for fid in ("001", "003", "017", "032", "260"):
            doc = r.family(fid)
            self.assertEqual(doc["id"], "f:" + fid)
            self.assertIn(doc["claim"]["state"], ("candidate", "unresolved"))

    def test_unresolved_headline_has_no_selected_statement(self):
        sel = R.Reader().family("260")["selection"]
        self.assertEqual(sel["headline_state"], "unresolved")
        self.assertIsNone(sel["headline_statement"])

    def test_receipt_reconstructs_to_its_digest(self):
        rc = R.Reader().number_receipt("families")
        self.assertEqual(rc["value"], 372)
        self.assertEqual(len(rc["members"]), 372)

    def test_unknown_sentence_key_stops(self):
        with self.assertRaises(R.ReaderError):
            R.Reader().number("no_such_number")

    def test_canonical_rows_are_not_vendored(self):
        with self.assertRaises(R.ReaderError):
            R.Reader().resolve({"path": "../rows/x.json", "pointer": "/row"})


class Tampering(unittest.TestCase):
    """Copy backend/ to a scratch directory, damage one thing, and expect a stop."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "backend"
        shutil.copytree(ROOT / "backend", self.root)
        self.r = R.Reader(root=self.root)
        self.logical = self.r.overview_family("003")["reader"]["path"]
        self.path = self.r.web / self.logical

    def tearDown(self):
        self.tmp.cleanup()

    def fresh(self):
        return R.Reader(root=self.root)

    def test_altered_bytes_stop(self):
        self.path.write_bytes(self.path.read_bytes().replace(b'"unresolved"', b'"candidate" '))
        with self.assertRaises(R.ReaderError):
            self.fresh().family("003")

    def test_packet_from_another_generation_stops(self):
        # Rewrite the packet's generation and patch the manifest so the bytes still match:
        # only the identity check can catch it.
        doc = json.loads(self.path.read_bytes())
        doc["generation_id"] = "sha256:" + "0" * 64
        raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.path.write_bytes(raw)
        mpath = self.r.web / "manifest.json"
        m = json.loads(mpath.read_text(encoding="utf-8"))
        m["assets"][self.logical].update(bytes=len(raw), sha256=R._sha(raw))
        mpath.write_text(json.dumps(m), encoding="utf-8")
        exp = json.loads((self.root / "EXPORT.json").read_text(encoding="utf-8"))
        exp["files"]["openai-math/web/manifest.json"]["sha256"] = R._sha(mpath.read_bytes())
        (self.root / "EXPORT.json").write_text(json.dumps(exp), encoding="utf-8")
        with self.assertRaises(R.ReaderError) as cm:
            self.fresh().family("003")
        self.assertIn("generation", str(cm.exception))

    def test_removed_packet_stops(self):
        self.path.unlink()
        with self.assertRaises(R.ReaderError):
            self.fresh().family("003")

    def test_altered_manifest_stops_at_load(self):
        mpath = self.r.web / "manifest.json"
        mpath.write_text(mpath.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaises(R.ReaderError):
            self.fresh()


if __name__ == "__main__":
    unittest.main(verbosity=1)
