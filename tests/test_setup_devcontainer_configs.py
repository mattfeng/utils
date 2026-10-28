import argparse
import base64
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from uvx_utils.setup_devcontainer_configs import (
    BASELINE_LABEL,
    ConfigFile,
    SetupError,
    managed_block,
    merge_content,
    render_config,
    resolve_conflict,
    setup_devcontainer_configs,
)


class MergeContentTests(unittest.TestCase):
    def test_independent_updates_preserve_user_edits(self):
        self.assertEqual(
            merge_content("a\nb\nc\n", "user\nb\nc\n", "a\nb\nnew\n"),
            "user\nb\nnew\n",
        )

    def test_user_deletion_and_new_defaults(self):
        self.assertEqual(
            merge_content("a\nb\nc\n", "a\nc\n", "a\nb\nc\nnew\n"),
            "a\nc\nnew\n",
        )

    def test_identical_edits_are_applied_once(self):
        self.assertEqual(
            merge_content("a\nb\nc\n", "shared\nb\nc\n", "shared\nb\nnew\n"),
            "shared\nb\nnew\n",
        )

    def test_conflicting_edits_require_review(self):
        for base, local, incoming in (
            ("a\n", "user\n", "new\n"),
            ("a\n", "user\na\n", "new\na\n"),
            ("a\nb\n", "", "a\nnew\nb\n"),
        ):
            with self.subTest(base=base, local=local, incoming=incoming):
                self.assertIsNone(merge_content(base, local, incoming))

    def test_unchanged_side_preserves_other_side(self):
        self.assertEqual(merge_content("a\n", "user\n", "a\n"), "user\n")
        self.assertEqual(merge_content("a\n", "a\n", "new\n"), "new\n")

    def test_legacy_content_requires_review_unless_it_matches(self):
        self.assertIsNone(merge_content(None, "user\n", "new\n"))
        self.assertEqual(merge_content(None, "new\n", "new\n"), "new\n")


class ConfigTrackingTests(unittest.TestCase):
    def setUp(self):
        self.spec = ConfigFile("Example", Path("/config"), "a\nb\nc\n", "# <--")

    def render(self, spec, existing):
        with patch("uvx_utils.setup_devcontainer_configs.read_config", return_value=existing):
            return render_config(spec)

    def test_each_format_tracks_defaults_and_is_idempotent(self):
        for prefix in ('" <--', "# <--", "<!--"):
            with self.subTest(prefix=prefix):
                spec = replace(self.spec, comment_prefix=prefix, content="# Unicode: café\n")
                initial = self.render(spec, None)
                encoded = base64.b64encode(spec.content.encode()).decode()
                self.assertIn(spec.comment(BASELINE_LABEL + encoded), initial.rendered_content)
                rerun = self.render(spec, initial.rendered_content)
                self.assertFalse(rerun.changed)
                self.assertFalse(rerun.conflict)

    def test_consecutive_updates_keep_customizations_and_outside_content(self):
        initial = "before\n" + managed_block(self.spec, "user\nb\nc\n") + "after\n"
        updated = replace(self.spec, content="a\nb\nnew\n")
        first = self.render(updated, initial)
        self.assertEqual(
            first.rendered_content,
            "before\n" + managed_block(updated, "user\nb\nnew\n") + "after\n",
        )
        self.assertFalse(self.render(updated, first.rendered_content).changed)
        newest = replace(updated, content="a\nnext\nnew\n")
        second = self.render(newest, first.rendered_content)
        self.assertEqual(
            second.rendered_content,
            "before\n" + managed_block(newest, "user\nnext\nnew\n") + "after\n",
        )

    def test_legacy_blocks_are_migrated_without_guessing(self):
        for content, conflict in ((self.spec.content, False), ("user\n", True)):
            with self.subTest(content=content):
                existing = f"{self.spec.begin_marker}\n{content}{self.spec.end_marker}\n"
                result = self.render(self.spec, existing)
                self.assertEqual(result.conflict, conflict)
                if conflict:
                    self.assertEqual(result.rendered_content, existing)
                else:
                    self.assertIn(BASELINE_LABEL, result.rendered_content)

    def test_unmanaged_content_is_preserved(self):
        result = self.render(self.spec, "personal config")
        self.assertEqual(
            result.rendered_content,
            "personal config\n\n" + managed_block(self.spec, self.spec.content),
        )

    def test_damaged_metadata_and_markers_are_rejected(self):
        valid = managed_block(self.spec, self.spec.content)
        encoded = base64.b64encode(self.spec.content.encode()).decode()
        for invalid in (
            valid.replace(encoded, "!!!"),
            valid.replace("Generated defaults", "user setting"),
            valid + valid,
            valid.replace(self.spec.end_marker, ""),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(SetupError):
                self.render(self.spec, invalid)

    def test_noninteractive_conflict_does_not_write_any_selected_config(self):
        args = argparse.Namespace(
            vim_config=Path("/vimrc"), omp_config=Path("/config.yml"),
            omp_keybindings=Path("/keybindings.yml"), omp_system_prompt=Path("/SYSTEM.md"),
            all=True, dry_run=False,
        )
        legacy = ConfigFile("Oh My Pi", args.omp_config, "", "# <--")
        existing = f"{legacy.begin_marker}\nuser edit\n{legacy.end_marker}\n"
        with (
            patch(
                "uvx_utils.setup_devcontainer_configs.read_config",
                side_effect=[None, existing, None, None],
            ),
            patch("uvx_utils.setup_devcontainer_configs.sys.stdin.isatty", return_value=False),
            patch("uvx_utils.setup_devcontainer_configs.write_atomically") as write,
            self.assertRaises(SetupError),
        ):
            setup_devcontainer_configs(args)
        write.assert_not_called()

    def test_keep_content_records_new_baseline_without_reprompting(self):
        installed = managed_block(self.spec, "user\nb\nc\n")
        incoming = replace(self.spec, content="new\nb\nc\n")
        conflict = self.render(incoming, installed)
        self.assertTrue(conflict.conflict)
        with (
            patch("uvx_utils.setup_devcontainer_configs.sys.stdin.isatty", return_value=True),
            patch("uvx_utils.setup_devcontainer_configs.sys.stdout") as output,
            patch("builtins.input", return_value="k"),
        ):
            output.isatty.return_value = True
            resolved = resolve_conflict(conflict)
        self.assertEqual(resolved.rendered_content, managed_block(incoming, "user\nb\nc\n"))
        self.assertFalse(self.render(incoming, resolved.rendered_content).changed)

    def test_generated_choice_preserves_outside_content(self):
        installed = "before\n" + managed_block(self.spec, "user\nb\nc\n") + "after\n"
        incoming = replace(self.spec, content="new\nb\nc\n")
        conflict = self.render(incoming, installed)
        with (
            patch("uvx_utils.setup_devcontainer_configs.sys.stdin.isatty", return_value=True),
            patch("uvx_utils.setup_devcontainer_configs.sys.stdout") as output,
            patch("builtins.input", return_value="g"),
        ):
            output.isatty.return_value = True
            resolved = resolve_conflict(conflict)
        self.assertEqual(
            resolved.rendered_content,
            "before\n" + managed_block(incoming, incoming.content) + "after\n",
        )

    def test_abort_is_the_default_conflict_choice(self):
        conflict = self.render(self.spec, managed_block(
            replace(self.spec, content="old\n"), "user\n",
        ))
        with (
            patch("uvx_utils.setup_devcontainer_configs.sys.stdin.isatty", return_value=True),
            patch("uvx_utils.setup_devcontainer_configs.sys.stdout") as output,
            patch("builtins.input", return_value=""),
            self.assertRaises(SetupError),
        ):
            output.isatty.return_value = True
            resolve_conflict(conflict)
