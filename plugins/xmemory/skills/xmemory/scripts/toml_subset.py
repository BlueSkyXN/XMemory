"""TOML 配置子集；沿用 1.4 解析器以支持 Python 3.9，不写文件。"""
from __future__ import annotations
import re
from typing import NoReturn

class TomlSubset:
    """只解析配置模板使用的 TOML 子集：注释、表头（含带引号的键）、字符串、整数、布尔、数组。

    不用 tomllib：它要 Python 3.11，而客户端里的 python3 常是系统自带的 3.9。所有解释器都走这一个
    解析器，同一份配置在哪个客户端读都一样；超出子集的写法明确报错，不去猜。
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

