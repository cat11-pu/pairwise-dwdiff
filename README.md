# dwdiff

一个纯内存、确定性的行级差异对比内核：LCS 动态规划求最小编辑脚本、按上下文行数
把脚本切成差异块、块头区间与块体渲染，以及一行内部的字符级高亮。两侧的行由调用
方按顺序喂入，内核不读文件、不读时钟、不起线程，也不做任何 I/O。

## 目录

- dwdiff/core.py：内核实现（最小编辑脚本、差异块合并、行内高亮、统一 diff 渲染）
- tests/test_core.py：内核的行为测试

## 怎么跑测试

在项目根目录执行：

    python3 -m unittest discover -s tests -v

Windows 上把 python3 换成你的解释器路径，例如：

    C:/Users/<你>/AppData/Local/Programs/Python/Python313/python.exe -m unittest discover -s tests -v
