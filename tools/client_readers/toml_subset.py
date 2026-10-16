"""TOML 配置子集；沿用 1.4 解析器以支持 Python 3.9，不写文件。"""
from __future__ import annotations
import re
from typing import NoReturn

class TomlSubset:
    """只解析配置模板使用的 TOML 子集：注释、表头（含带引号的键）、字符串、整数、布尔、数组。

    runtime 在没有 tomllib 时使用本解析器。parse 拒绝超出子集的值；top_level
    仅解析指定顶层键，跳过其他值，供自动化配置的归属读取使用。
    """
    BARE = re.compile(r"[A-Za-z0-9_-]+")
    TOKEN = re.compile(r"[^\s,\]#]+")
    INTEGER = re.compile(r"[+-]?(?:0|[1-9](?:_?[0-9])*)")
    ESCAPES = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r", '"': '"', "\\": "\\"}

    def __init__(self, text: str, name: str = "config.toml"):
        self.s, self.i, self.name = text.replace("\r\n", "\n"), 0, name

    def error(self, message: str) -> NoReturn:
        line = self.s.count("\n", 0, self.i) + 1
        raise ValueError(f"{self.name} 第 {line} 行：{message}（只支持表、字符串、整数、布尔和数组）")

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def skip(self, newlines: bool = False):
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in " \t" or (newlines and c == "\n"):
                self.i += 1
            elif c == "#":
                end = self.s.find("\n", self.i)
                self.i = len(self.s) if end < 0 else end
            else:
                return

    def parse(self) -> dict:
        root: dict = {}
        current, defined = root, set()
        while True:
            self.skip(newlines=True)
            if not self.peek():
                return root
            if self.peek() == "[":
                if self.s.startswith("[[", self.i):
                    self.error("不支持表数组 [[…]]")
                self.i += 1
                path = self.key_path("]")
                if path in defined:
                    self.error(f"表重复定义：{'.'.join(path)}")
                defined.add(path)
                current = root
                for part in path:
                    current = current.setdefault(part, {})
                    if not isinstance(current, dict):
                        self.error(f"{part} 已经是值，不能再当表")
            else:
                path = self.key_path("=")
                if len(path) != 1:
                    self.error("不支持点号键（a.b = …），请改用表头")
                self.skip()
                value = self.value()
                if path[0] in current:
                    self.error(f"键重复：{path[0]}")
                current[path[0]] = value
            self.skip()
            if self.peek() not in ("", "\n"):
                self.error("一行只能有一个键值或表头")

    def key_path(self, terminator: str) -> tuple:
        parts = []
        while True:
            self.skip()
            if self.peek() == '"':
                parts.append(self.basic_string())
            elif self.peek() == "'":
                parts.append(self.literal_string())
            else:
                m = self.BARE.match(self.s, self.i)
                if not m:
                    self.error("键名无效")
                parts.append(m.group(0))
                self.i = m.end()
            self.skip()
            if self.peek() == ".":
                self.i += 1
                continue
            if self.peek() != terminator:
                self.error(f"缺少 {terminator}")
            self.i += 1
            return tuple(parts)

    def top_level(self, keys) -> dict:
        """只取第一个表头前的指定键；其他值按字符串与容器边界整体跳过。"""
        result = {}
        while True:
            self.skip(newlines=True)
            if self.peek() in ("", "["):
                return result
            path = self.key_path("=")
            self.skip()
            if len(path) == 1 and path[0] in keys:
                if path[0] in result:
                    self.error(f"键重复：{path[0]}")
                result[path[0]] = self.value()
            else:
                self.skip_value()
            self.skip()
            if self.peek() not in ("", "\n"):
                self.error("一行只能有一个键值")

    def skip_value(self):
        """跳过不参与归属的值，不解释其类型；不把值内的诱饵行当成键。"""
        closing = []
        while self.peek():
            c = self.peek()
            if c in "\"'":
                quote = c
                multiline = self.s.startswith(quote * 3, self.i)
                self.i += 3 if multiline else 1
                while True:
                    c = self.peek()
                    if not c or (not multiline and c == "\n"):
                        self.error("字符串缺少结束引号")
                    if quote == '"' and c == "\\":
                        self.i += 2
                        continue
                    if multiline and self.s.startswith(quote * 3, self.i):
                        # TOML 允许结束三引号前保留一个或两个相同引号。
                        self.i += 3
                        for _ in range(2):
                            if self.peek() == quote:
                                self.i += 1
                        break
                    self.i += 1
                    if not multiline and c == quote:
                        break
            elif c in "[{":
                closing.append("]" if c == "[" else "}")
                self.i += 1
            elif c in "]}":
                if not closing or c != closing.pop():
                    self.error("容器结束符不匹配")
                self.i += 1
            elif c == "#":
                self.skip()
            elif c == "\n" and not closing:
                return
            else:
                self.i += 1
        if closing:
            self.error("容器缺少结束符")

    def value(self):
        c = self.peek()
        if self.s.startswith(('"""', "'''"), self.i):
            self.error("不支持多行字符串")
        if c == '"':
            return self.basic_string()
        if c == "'":
            return self.literal_string()
        if c == "[":
            return self.array()
        if c == "{":
            self.error("不支持内联表 {…}")
        m = self.TOKEN.match(self.s, self.i)
        token = m.group(0) if m else ""
        if token in ("true", "false"):
            self.i += len(token)
            return token == "true"
        if self.INTEGER.fullmatch(token):
            self.i += len(token)
            return int(token.replace("_", ""))
        self.error(f"不支持的值：{token or c!r}")

    def basic_string(self) -> str:
        self.i += 1
        out = []
        while True:
            c = self.peek()
            if c in ("", "\n"):
                self.error("字符串缺少结束引号")
            self.i += 1
            if c == '"':
                return "".join(out)
            if c == "\\":
                e = self.peek()
                self.i += 1
                if e in self.ESCAPES:
                    out.append(self.ESCAPES[e])
                    continue
                width = {"u": 4, "U": 8}.get(e)
                digits = self.s[self.i:self.i + width] if width else ""
                if not width or not re.fullmatch(r"[0-9A-Fa-f]{%d}" % width, digits):
                    self.error(f"不支持的转义：\\{e}")
                code = int(digits, 16)
                if 0xD800 <= code <= 0xDFFF or code > 0x10FFFF:
                    self.error(f"转义不是合法字符：\\{e}{digits}")
                out.append(chr(code))
                self.i += width
            elif (c < " " and c != "\t") or c == "\x7f":
                self.error("字符串里有控制字符")
            else:
                out.append(c)

    def literal_string(self) -> str:
        end, newline = self.s.find("'", self.i + 1), self.s.find("\n", self.i + 1)
        if end < 0 or 0 <= newline < end:
            self.error("字符串缺少结束引号")
        text = self.s[self.i + 1:end]
        self.i = end + 1
        return text

    def array(self) -> list:
        self.i += 1
        items = []
        while True:
            self.skip(newlines=True)
            if self.peek() == "]":
                self.i += 1
                return items
            if not self.peek():
                self.error("数组缺少结束的 ]")
            items.append(self.value())
            self.skip(newlines=True)
            if self.peek() == ",":
                self.i += 1
            elif self.peek() != "]":
                self.error("数组元素之间要用逗号分隔")
