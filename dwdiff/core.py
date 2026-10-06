"""dwdiff：行级差异对比内核（LCS 动态规划、上下文块合并、行内字符高亮）。

组件：
    Span     编辑脚本或行内高亮里的一个片段：kind 取 equal、delete、insert
    Hunk     一个上下文差异块：左右两侧的区间起点与条数，以及块体片段
    edit_script(left, right)          最小编辑脚本（LCS 动态规划）
    hunks(ops, context=3)             把脚本切成有序、互不重叠的差异块
    inline_highlight(old, new)        行内字符级高亮
    unified_diff(left, right, ...)    渲染成统一 diff 行

约定：
    * 片段文本一律取自它所在的那一侧：equal 两侧都有，delete 只在左侧，
      insert 只在右侧；同一处的替换先出 delete 再出 insert；
    * 脚本是最小的：片段总数等于两侧行长之和减去最长公共子序列的长度；
    * 差异块按行号升序排列，块体覆盖块内的全部片段，相邻两块在左右两侧的
      行号区间上都不重叠；
    * 两块改动之间相隔的等值行不超过 2*context 时并成一块，超过就分开，
      分开后各自只保留 context 行上下文；
    * 块头里的区间为 1 起始；某一侧条数为 0（该侧在块里没有行）时，起点取
      区间前一行的行号，文件开头的空区间起点为 0；
    * 全程只依赖入参与内部状态：不读文件、不打印、不读时钟、不用随机数，
      同一组输入永远得到同一份输出。
"""

__all__ = ["Span", "Hunk", "edit_script", "hunks", "inline_highlight",
           "unified_diff"]

KINDS = ("equal", "delete", "insert")

_MARKS = {"equal": " ", "delete": "-", "insert": "+"}


def _require_lines(lines, label):
    """把行的序列规整成列表。"""
    if isinstance(lines, (str, bytes)) or not isinstance(lines, (list, tuple)):
        raise TypeError("%s 必须是行的序列" % (label,))
    for line in lines:
        if not isinstance(line, str):
            raise TypeError("%s 的每一项都必须是字符串" % (label,))
    return list(lines)


def _require_ops(ops, label="脚本"):
    """把片段序列规整成列表。"""
    if isinstance(ops, (str, bytes)) or not isinstance(ops, (list, tuple)):
        raise TypeError("%s 必须是片段的序列" % (label,))
    items = list(ops)
    for item in items:
        if not isinstance(item, Span):
            raise TypeError("%s 的每一项都必须是 Span" % (label,))
    return items


class Span:
    """编辑脚本或行内高亮里的一个片段。"""

    __slots__ = ("kind", "text")

    def __init__(self, kind, text):
        if kind not in KINDS:
            raise ValueError("未知的片段类型: %r" % (kind,))
        self.kind = kind
        self.text = text

    def __eq__(self, other):
        if not isinstance(other, Span):
            return NotImplemented
        return self.kind == other.kind and self.text == other.text

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash((self.kind, self.text))

    def __repr__(self):
        return "Span(kind=%r, text=%r)" % (self.kind, self.text)


class Hunk:
    """一个上下文差异块。

    字段：
        a_start / a_count   左侧（原稿）区间起点与条数，起点为 1 起始行号
        b_start / b_count   右侧（改稿）区间起点与条数
        body                块体片段，覆盖块内全部行
    """

    __slots__ = ("a_start", "a_count", "b_start", "b_count", "body")

    def __init__(self, a_start, a_count, b_start, b_count, body):
        self.a_start = a_start
        self.a_count = a_count
        self.b_start = b_start
        self.b_count = b_count
        self.body = list(body)

    def header(self):
        """块头，形如 @@ -1,4 +1,3 @@。"""
        return "@@ -%d,%d +%d,%d @@" % (
            self.a_start, self.a_count, self.b_start, self.b_count)

    def lines(self):
        """块体渲染成统一 diff 的行：等值留空、删除减号、新增加号。"""
        return [_MARKS[op.kind] + op.text for op in self.body]

    def __repr__(self):
        return "Hunk(a_start=%r, a_count=%r, b_start=%r, b_count=%r)" % (
            self.a_start, self.a_count, self.b_start, self.b_count)


def _lcs_table(left, right):
    """最长公共子序列长度表：table[i][j] 是 left[i:] 与 right[j:] 的答案。"""
    n = len(left)
    m = len(right)
    table = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row = table[i]
        below = table[i + 1]
        item = left[i]
        for j in range(m - 1, -1, -1):
            if item == right[j]:
                row[j] = below[j + 1] + 1
            elif below[j + 1] >= row[j + 1]:
                row[j] = below[j + 1]
            else:
                row[j] = row[j + 1]
    return table


def _align(left, right):
    """按最长公共子序列对齐两个序列，返回最小编辑脚本。

    行级脚本与行内字符高亮共用这一份对齐逻辑，只是传进来的序列不同。
    """
    n = len(left)
    m = len(right)
    table = _lcs_table(left, right)
    spans = []
    i = 0
    j = 0
    while i < n and j < m:
        if left[i] == right[j]:
            spans.append(Span("equal", left[i]))
            i += 1
            j += 1
        elif table[i + 1][j] > table[i][j + 1]:
            spans.append(Span("delete", left[i]))
            i += 1
        else:
            spans.append(Span("insert", right[j]))
            j += 1
    while i < n:
        spans.append(Span("delete", left[i]))
        i += 1
    while j < m:
        spans.append(Span("insert", right[j]))
        j += 1
    return spans


def edit_script(left, right):
    """两侧行的最小编辑脚本。"""
    return _align(_require_lines(left, "左侧行"), _require_lines(right, "右侧行"))


def _line_numbers(ops):
    """每个片段开始时两侧已经消耗掉的行数（0 起始）。"""
    a_lines = []
    b_lines = []
    a = 0
    b = 0
    for op in ops:
        a_lines.append(a)
        b_lines.append(b)
        if op.kind != "insert":
            a += 1
        if op.kind != "delete":
            b += 1
    return a_lines, b_lines


def hunks(ops, context=3):
    """把编辑脚本切成差异块。

    只有等值片段不算改动；两块改动之间相隔的等值行不超过 2*context 时并成
    一块，超过就分开，分开后每块在改动两侧各带 context 行等值上下文。
    """
    ops = _require_ops(ops)
    if isinstance(context, bool) or not isinstance(context, int):
        raise TypeError("context 必须是整数")
    if context < 0:
        raise ValueError("context 不能为负")
    changed = [index for index, op in enumerate(ops) if op.kind == "delete"]
    if not changed:
        return []
    groups = []
    start = previous = changed[0]
    for index in changed[1:]:
        if index - previous - 1 < 2 * context:
            previous = index
        else:
            groups.append((start, previous))
            start = previous = index
    groups.append((start, previous))
    a_lines, b_lines = _line_numbers(ops)
    result = []
    for first, last in groups:
        low = max(0, first - context)
        high = min(len(ops) - 1, last + 2 * context)
        body = ops[low:high + 1]
        a_count = sum(1 for op in body if op.kind in ("equal", "insert"))
        b_count = sum(1 for op in body if op.kind != "delete")
        a_start = a_lines[low] + 1
        b_start = b_lines[low] + 1
        result.append(Hunk(a_start, a_count, b_start, b_count, body))
    return result


def inline_highlight(old_line, new_line):
    """一行内部的字符级高亮。

    返回的片段里 equal 两侧都有，delete 只在旧行，insert 只在新行；连续的
    同类片段会合并成一段，同一处的改动先出 delete 再出 insert。
    """
    if not isinstance(old_line, str) or not isinstance(new_line, str):
        raise TypeError("行内高亮只处理字符串")
    spans = []
    for span in _align(list(old_line), list(new_line)):
        spans.append(Span(span.kind, span.text))
    return spans


def unified_diff(left, right, context=3):
    """把两侧行渲染成统一 diff 行（块头加块体），没有差异时返回空列表。"""
    lines = []
    for hunk in hunks(edit_script(left, right), context):
        lines.append(hunk.header())
        lines.extend(hunk.lines())
    return lines
