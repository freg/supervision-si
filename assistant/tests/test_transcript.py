# -*- coding: utf-8 -*-
"""#767 : transcription d'une session en Markdown (secrets masqués, table d'anonymisation)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import transcript_to_md as t  # noqa: E402

LINES = [
    {"type": "user", "timestamp": "2026-10-14T13:47:00Z", "message": {"content": "<system-reminder>bruit</system-reminder>pve10 en alerte disque, mot de passe : s3cr3tXY"}},
    {"type": "assistant", "timestamp": "2026-10-14T13:48:00Z", "message": {"content": [{"type": "thinking", "thinking": "x"}, {"type": "text", "text": "Diagnostic sur srv.exemple.fr :"},
                                                                                       {"type": "tool_use", "id": "u1", "name": "mcp__remote-devices__device_bash", "input": {"command": "df -h"}}]}},
    {"type": "user", "timestamp": "2026-10-14T13:48:05Z", "message": {"content": [{"type": "tool_result", "tool_use_id": "u1", "is_error": True, "content": "Permission denied token=abcd1234efgh"}]}},
    {"type": "user", "timestamp": "2026-10-15T08:00:00Z", "message": {"content": "This session is being continued from a previous conversation. Résumé…"}},
    {"type": "frame-link"},
]


class Transcript(unittest.TestCase):
    def test_convert(self):
        md = t.convert([json.dumps(x) for x in LINES], {"srv.exemple.fr": "hote-a"})
        self.assertIn("## 2026-10-14", md); self.assertIn("## 2026-10-15", md)
        self.assertNotIn("bruit", md); self.assertNotIn("s3cr3tXY", md); self.assertNotIn("abcd1234efgh", md)
        self.assertIn("«masqué»", md); self.assertIn("hote-a", md); self.assertNotIn("srv.exemple.fr", md)
        self.assertIn("outil `device_bash`", md); self.assertIn("⚠ résultat en erreur", md); self.assertIn("Résumé de contexte", md)
        self.assertNotIn("device_bash", t.convert([json.dumps(x) for x in LINES], tools=False))

    def test_redact(self):
        self.assertEqual(t.redact("Authorization: Bearer abc.def"), "Authorization: Bearer «masqué»")
        self.assertIn("«clé privée masquée»", t.redact("-----BEGIN OPENSSH PRIVATE KEY-----\nxx\n-----END OPENSSH PRIVATE KEY-----"))


if __name__ == "__main__":
    unittest.main()
