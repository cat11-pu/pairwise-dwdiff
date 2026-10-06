"""dwdiff：行级差异对比内核。

对外入口：
    Span              编辑脚本或行内高亮里的一个片段
    Hunk              一个上下文差异块
    edit_script       两侧行的最小编辑脚本
    hunks             把脚本切成有序、互不重叠的差异块
    inline_highlight  一行内部的字符级高亮
    unified_diff      渲染成统一 diff 行
"""

from .core import Hunk, Span, edit_script, hunks, inline_highlight, unified_diff

__all__ = [
    "Hunk",
    "Span",
    "edit_script",
    "hunks",
    "inline_highlight",
    "unified_diff",
]
