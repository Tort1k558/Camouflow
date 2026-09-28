"""Small native Python highlighter for the scenario editor."""

import keyword
import re

from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


class PythonHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):  # noqa: N802
        self.setCurrentBlockState(0)
        rules = [
            (r"\b(?:" + "|".join(keyword.kwlist) + r")\b", "#8055b5"),
            (r"\b\d+(?:\.\d+)?\b", "#94671c"),
            (r"\b(?:ctx|page|context|inputs|variables)\b", "#237b8b"),
            (r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')''', "#3f714a"),
            (r"#.*", "#7d867c"),
        ]
        for pattern, color in rules:
            style = QTextCharFormat()
            style.setForeground(QColor(color))
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), style)
        style = QTextCharFormat()
        style.setForeground(QColor("#3f714a"))
        state = self.previousBlockState()
        start = 0
        while start < len(text):
            if state not in {1, 2}:
                matches = [(text.find(delimiter, start), index, delimiter) for index, delimiter in [(1, "'''"), (2, '"""')]]
                matches = [row for row in matches if row[0] >= 0]
                if not matches:
                    break
                begin, state, delimiter = min(matches)
                end = text.find(delimiter, begin + 3)
            else:
                begin = start
                delimiter = "'''" if state == 1 else '"""'
                end = text.find(delimiter, start)
            if end < 0:
                self.setFormat(begin, len(text) - begin, style)
                self.setCurrentBlockState(state)
                break
            self.setFormat(begin, end + 3 - begin, style)
            start, state = end + 3, 0
