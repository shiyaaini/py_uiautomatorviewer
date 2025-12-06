from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt5.QtCore import Qt, QRegExp

class JSHighlighter(QSyntaxHighlighter):
    def __init__(self, document, api_keywords=None):
        super().__init__(document)
        self.rules = []
        self.api_keywords = api_keywords or []
        self._init_formatting()

    def _init_formatting(self):
        # 1. Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))  # VSCode Blue
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "function", "var", "let", "const", "if", "else", "for", "while", 
            "do", "return", "break", "continue", "switch", "case", "default", 
            "new", "this", "true", "false", "null", "undefined", "try", "catch", 
            "finally", "throw", "import", "export", "class", "extends", "super"
        ]
        for word in keywords:
            pattern = QRegExp(r"\b" + word + r"\b")
            self.rules.append((pattern, keyword_format))

        # 2. AutoJs API Objects (if provided)
        if self.api_keywords:
            api_format = QTextCharFormat()
            api_format.setForeground(QColor("#4EC9B0"))  # VSCode Teal for classes/objects
            for word in self.api_keywords:
                pattern = QRegExp(r"\b" + word + r"\b")
                self.rules.append((pattern, api_format))

        # 3. Strings ("..." and '...')
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))  # VSCode Orange
        self.rules.append((QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
        self.rules.append((QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))

        # 4. Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))  # VSCode Light Green
        self.rules.append((QRegExp(r"\b\d+(\.\d+)?\b"), number_format))

        # 5. Comments
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6A9955"))  # VSCode Green
        # Single line //
        self.rules.append((QRegExp(r"//[^\n]*"), self.comment_format))
        
        # Multi-line /* ... */ (handled in highlightBlock)
        self.comment_start = QRegExp(r"/\*")
        self.comment_end = QRegExp(r"\*/")

    def highlightBlock(self, text):
        # Apply regular rules
        for pattern, format in self.rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        # Handle multi-line comments
        self.setCurrentBlockState(0)
        
        start_index = 0
        if self.previousBlockState() != 1:
            start_index = self.comment_start.indexIn(text)
        
        while start_index >= 0:
            end_index = self.comment_end.indexIn(text, start_index)
            comment_length = 0
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + self.comment_end.matchedLength()
            
            self.setFormat(start_index, comment_length, self.comment_format)
            start_index = self.comment_start.indexIn(text, start_index + comment_length)
