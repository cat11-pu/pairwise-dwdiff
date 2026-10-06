"""dwdiff.core 的行为测试：编辑脚本、差异块合并与行内高亮。"""

import unittest

from dwdiff.core import Span, edit_script, hunks, inline_highlight, unified_diff


def kinds_of(spans):
    """片段序列的 (kind, text) 列表，便于整段比对。"""
    return [(span.kind, span.text) for span in spans]


class DwdiffCoreTest(unittest.TestCase):
    """行级差异对比内核。"""

    def test_identical_inputs_have_no_differences(self):
        """两侧完全相同时：脚本全是等值、没有差异块、渲染为空。"""
        lines = ["alpha", "beta", "gamma"]
        script = edit_script(list(lines), list(lines))
        self.assertEqual(kinds_of(script),
                         [("equal", "alpha"), ("equal", "beta"), ("equal", "gamma")])
        self.assertEqual(hunks(script), [])
        self.assertEqual(unified_diff(list(lines), list(lines)), [])
        self.assertEqual(unified_diff([], []), [])

    def test_edit_script_reconstructs_both_sides(self):
        """脚本可还原两侧：等值加删除拼出左侧，等值加新增拼出右侧。"""
        cases = [
            (["alpha", "beta", "gamma"], ["alpha", "delta", "gamma"]),
            (["one", "two"], ["one", "two", "three"]),
            (["x", "y", "z"], ["y"]),
            (["a", "b", "c"], []),
            ([], ["a", "b"]),
            (["head", "body", "tail"], ["head", "middle", "body", "tail"]),
        ]
        for left, right in cases:
            script = edit_script(list(left), list(right))
            self.assertEqual([s.text for s in script if s.kind in ("equal", "delete")],
                             left)
            self.assertEqual([s.text for s in script if s.kind in ("equal", "insert")],
                             right)

    def test_script_stays_minimal_when_the_tail_already_matches(self):
        """块的末尾已经对得上时，前面的行直接删掉，不要删了再在末尾补回来。"""
        left = ["", "first paragraph", "second paragraph", ""]
        right = ["second paragraph", ""]
        script = edit_script(left, right)
        self.assertEqual(len(script), 4)
        self.assertEqual(sorted(kinds_of(script)),
                         [("delete", ""), ("delete", "first paragraph"),
                          ("equal", ""), ("equal", "second paragraph")])

    def test_replacement_lists_deletion_before_insertion(self):
        """替换先出删除再出新增，整行如此，渲染出来的块体也如此。"""
        script = edit_script(["legacy line"], ["shiny line"])
        self.assertEqual(kinds_of(script),
                         [("delete", "legacy line"), ("insert", "shiny line")])
        self.assertEqual(unified_diff(["alpha", "beta", "legacy"],
                                      ["alpha", "beta", "shiny"]),
                         ["@@ -1,3 +1,3 @@", " alpha", " beta",
                          "-legacy", "+shiny"])

    def test_nearby_changes_share_one_hunk(self):
        """相隔不超过两倍上下文的改动并成一块，超过就分开。"""
        merged = hunks(edit_script(["L1", "L2", "L3", "L4", "L5"], ["L1", "L3", "L4"]), 1)
        self.assertEqual(len(merged), 1)
        self.assertEqual((merged[0].a_start, merged[0].b_start), (1, 1))
        self.assertEqual(merged[0].lines(), [" L1", "-L2", " L3", " L4", "-L5"])

        apart = hunks(edit_script(["L1", "L2", "L3", "L4", "L5", "L6"],
                                  ["L1", "L3", "L4", "L5"]), 1)
        self.assertEqual(len(apart), 2)
        self.assertEqual([hunk.a_start for hunk in apart], [1, 5])

    def test_empty_side_range_starts_at_zero(self):
        """一侧没有行时，块头里的起点取区间前一行：整份删除的右侧从 0 起。"""
        self.assertEqual(unified_diff(["only line"], []), ["@@ -1,1 +0,0 @@", "-only line"])

    def test_insert_only_change_forms_a_hunk(self):
        """只有新增、没有删除的改动同样要成块，且块体覆盖到插入的行。"""
        self.assertEqual(unified_diff(["alpha", "beta"], ["alpha", "x", "y", "beta"], 1),
                         ["@@ -1,2 +1,4 @@", " alpha", "+x", "+y", " beta"])

    def test_hunk_header_counts_lines_of_that_side(self):
        """块头两侧的条数只数各自那一侧的行，与块体逐行对得上。"""
        self.assertEqual(unified_diff(["alpha", "legacy", "tail"], ["alpha", "tail"]),
                         ["@@ -1,3 +1,2 @@", " alpha", "-legacy", " tail"])
        self.assertEqual(unified_diff(["one", "two", "three"], ["one"]),
                         ["@@ -1,3 +1,1 @@", " one", "-two", "-three"])

    def test_hunk_context_does_not_overlap_the_next_hunk(self):
        """分开的差异块各带自己的上下文，行号区间不许叠在一起。"""
        left = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        right = ["a", "c", "d", "e", "f", "g", "i", "j"]
        blocks = hunks(edit_script(left, right), 2)
        self.assertEqual(len(blocks), 2)
        self.assertEqual([hunk.a_start for hunk in blocks], [1, 6])
        self.assertEqual(blocks[0].lines(), [" a", "-b", " c", " d"])
        self.assertEqual(blocks[1].lines(), [" f", " g", "-h", " i", " j"])
        self.assertLessEqual(blocks[0].a_start + len(blocks[0].lines()),
                             blocks[1].a_start)

    def test_inline_highlight_marks_changed_runs(self):
        """行内高亮把连续的改动并成一段，同一处先删后插，相同行整行等值。"""
        self.assertEqual(kinds_of(inline_highlight("value = 1", "value = 2")),
                         [("equal", "value = "), ("delete", "1"), ("insert", "2")])
        self.assertEqual(kinds_of(inline_highlight("abcde", "abXYe")),
                         [("equal", "ab"), ("delete", "cd"), ("insert", "XY"),
                          ("equal", "e")])
        self.assertEqual(inline_highlight("same", "same"), [Span("equal", "same")])


if __name__ == "__main__":
    unittest.main()
