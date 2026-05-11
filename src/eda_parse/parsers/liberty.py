"""Liberty (.lib) parser.

Liberty is a structured data format used to characterize standard-cell
libraries for synthesis, timing, and power. Spec lives with Synopsys
(Liberty NCX/Reference Manual); the language has only three kinds of
statements:

* Group:               ``name ( args? ) { body }``
* Simple attribute:    ``key : value ;``
* Complex attribute:   ``key ( arg, arg, ... ) ;``

Plus C-style ``/* ... */`` comments and ``\\``-newline line continuation
(both at top level between tokens and inside double-quoted strings).

This module implements a hand-rolled tokenizer and a recursive-descent
parser that produce an AST of :class:`Group`, :class:`Attr`, and
:class:`ComplexAttr` nodes, then folds that AST into a
:class:`~eda_parse.types.ParsedDocument` with one :class:`Chunk` per
``cell`` group. Library-level metadata (technology, units, default
operating conditions, cell count, pin count, PVT corner) is extracted
into the document-level metadata dict; per-cell metadata (area, function,
pin direction map, leakage power) is extracted into each chunk's metadata.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from pathlib import Path

from eda_parse.types import Chunk, ParsedDocument

# ----------------------------------------------------------------------
# AST
# ----------------------------------------------------------------------

Value = str | float | int


@dataclass
class Attr:
    """A simple ``key : value ;`` attribute."""

    name: str
    value: Value


@dataclass
class ComplexAttr:
    """A complex ``key ( arg, arg, ... ) ;`` attribute."""

    name: str
    args: list[Value] = field(default_factory=list)


@dataclass
class Group:
    """A ``name ( args? ) { body }`` group."""

    name: str
    args: list[Value] = field(default_factory=list)
    body: list[Group | Attr | ComplexAttr] = field(default_factory=list)


# ----------------------------------------------------------------------
# Tokenizer
# ----------------------------------------------------------------------

# Token kinds. Using a tiny set instead of an enum for speed and brevity.
_T_LBRACE = "{"
_T_RBRACE = "}"
_T_LPAREN = "("
_T_RPAREN = ")"
_T_COMMA = ","
_T_COLON = ":"
_T_SEMI = ";"
_T_STRING = "STR"
_T_NUMBER = "NUM"
_T_WORD = "WORD"

_PUNCT = {"{", "}", "(", ")", ",", ":", ";"}

# Word characters: identifiers, unquoted values like "1ns", "true", expression-y
# strings like "(!A * !Y)" usually come quoted but unquoted tokens contain a wide
# alphabet in practice (digits, dots, plus, minus, underscore, slash, percent).
_WORD_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789.+-/%@!*"
)

_NUMBER_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")


@dataclass
class _Token:
    kind: str
    text: str
    line: int


class LibertyParseError(ValueError):
    """Raised when a Liberty file cannot be parsed."""


def _tokenize(src: str) -> list[_Token]:
    """Return a flat list of tokens. Strips comments and folds line
    continuations both at top level and inside strings.
    """
    toks: list[_Token] = []
    i = 0
    n = len(src)
    line = 1

    while i < n:
        c = src[i]

        # Newline
        if c == "\n":
            line += 1
            i += 1
            continue

        # Whitespace
        if c in " \t\r":
            i += 1
            continue

        # Line continuation at top level: '\' followed by newline
        if c == "\\" and i + 1 < n and src[i + 1] == "\n":
            line += 1
            i += 2
            continue

        # C-style comment
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            if j == -1:
                raise LibertyParseError(f"unterminated /* */ comment at line {line}")
            line += src.count("\n", i, j + 2)
            i = j + 2
            continue

        # Quoted string (supports backslash-newline continuation)
        if c == '"':
            j = i + 1
            buf: list[str] = []
            start_line = line
            while j < n:
                cj = src[j]
                if cj == '"':
                    break
                if cj == "\\" and j + 1 < n and src[j + 1] == "\n":
                    line += 1
                    j += 2
                    continue
                if cj == "\n":
                    line += 1
                buf.append(cj)
                j += 1
            else:
                raise LibertyParseError(
                    f"unterminated string starting at line {start_line}"
                )
            toks.append(_Token(_T_STRING, "".join(buf), start_line))
            i = j + 1
            continue

        # Punctuation
        if c in _PUNCT:
            toks.append(_Token(c, c, line))
            i += 1
            continue

        # Word / number
        if c in _WORD_CHARS:
            j = i
            while j < n and src[j] in _WORD_CHARS:
                j += 1
            text = src[i:j]
            kind = _T_NUMBER if _NUMBER_RE.match(text) else _T_WORD
            toks.append(_Token(kind, text, line))
            i = j
            continue

        raise LibertyParseError(
            f"unexpected character {c!r} at line {line}"
        )

    return toks


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------


def _coerce_value(tok: _Token) -> Value:
    """Turn a single token into its Python value."""
    if tok.kind == _T_NUMBER:
        text = tok.text
        if "." in text or "e" in text or "E" in text:
            return float(text)
        return int(text)
    return tok.text


class _Parser:
    def __init__(self, toks: list[_Token]) -> None:
        self.toks = toks
        self.i = 0

    def _peek(self, offset: int = 0) -> _Token | None:
        idx = self.i + offset
        if idx >= len(self.toks):
            return None
        return self.toks[idx]

    def _eat(self, kind: str | None = None) -> _Token:
        tok = self._peek()
        if tok is None:
            raise LibertyParseError("unexpected end of input")
        if kind is not None and tok.kind != kind:
            raise LibertyParseError(
                f"expected {kind!r} but got {tok.kind!r} {tok.text!r} at line {tok.line}"
            )
        self.i += 1
        return tok

    def parse_top(self) -> Group:
        """The top of a Liberty file is a single ``library (...) { ... }`` group."""
        return self._parse_group()

    def _parse_group(self) -> Group:
        name_tok = self._eat(_T_WORD)
        self._eat(_T_LPAREN)
        args = self._parse_args_until_rparen()
        self._eat(_T_RPAREN)
        self._eat(_T_LBRACE)
        body = self._parse_body()
        self._eat(_T_RBRACE)
        return Group(name=name_tok.text, args=args, body=body)

    def _parse_args_until_rparen(self) -> list[Value]:
        out: list[Value] = []
        tok = self._peek()
        if tok is not None and tok.kind == _T_RPAREN:
            return out
        while True:
            tok = self._eat()
            if tok.kind not in (_T_WORD, _T_NUMBER, _T_STRING):
                raise LibertyParseError(
                    f"expected argument but got {tok.kind!r} {tok.text!r} at line {tok.line}"
                )
            out.append(_coerce_value(tok))
            nxt = self._peek()
            if nxt is None:
                raise LibertyParseError("unexpected end of input in argument list")
            if nxt.kind == _T_COMMA:
                self.i += 1
                continue
            break
        return out

    def _parse_body(self) -> list[Group | Attr | ComplexAttr]:
        body: list[Group | Attr | ComplexAttr] = []
        while True:
            tok = self._peek()
            if tok is None:
                raise LibertyParseError("unexpected end of input inside group body")
            if tok.kind == _T_RBRACE:
                break
            body.append(self._parse_statement())
        return body

    def _parse_statement(self) -> Group | Attr | ComplexAttr:
        # Always starts with a WORD; the next token disambiguates:
        #   WORD ':' ...             -> simple attribute
        #   WORD '(' ... ')' '{' ... -> group
        #   WORD '(' ... ')' ';'     -> complex attribute
        name_tok = self._eat(_T_WORD)
        nxt = self._peek()
        if nxt is None:
            raise LibertyParseError(f"unexpected end of input after {name_tok.text!r}")

        if nxt.kind == _T_COLON:
            self.i += 1
            value_tok = self._eat()
            if value_tok.kind not in (_T_WORD, _T_NUMBER, _T_STRING):
                raise LibertyParseError(
                    f"expected value for {name_tok.text!r} at line {value_tok.line}"
                )
            # Optional trailing semicolon (Liberty doesn't strictly require one
            # for simple attrs but most writers emit it).
            after = self._peek()
            if after is not None and after.kind == _T_SEMI:
                self.i += 1
            return Attr(name=name_tok.text, value=_coerce_value(value_tok))

        if nxt.kind == _T_LPAREN:
            self.i += 1
            args = self._parse_args_until_rparen()
            self._eat(_T_RPAREN)
            after = self._peek()
            if after is None:
                raise LibertyParseError(
                    f"unexpected end of input after {name_tok.text!r}(...)"
                )
            if after.kind == _T_LBRACE:
                self.i += 1
                body = self._parse_body()
                self._eat(_T_RBRACE)
                return Group(name=name_tok.text, args=args, body=body)
            if after.kind == _T_SEMI:
                self.i += 1
                return ComplexAttr(name=name_tok.text, args=args)
            # Some writers omit the trailing semicolon on complex attributes.
            return ComplexAttr(name=name_tok.text, args=args)

        raise LibertyParseError(
            f"unexpected token after {name_tok.text!r}: {nxt.kind!r} {nxt.text!r} "
            f"at line {nxt.line}"
        )


# ----------------------------------------------------------------------
# AST -> ParsedDocument
# ----------------------------------------------------------------------


def _find_attr(group: Group, name: str) -> Value | None:
    """Find a simple ``key : value`` attribute, OR a complex attribute with a
    single argument (e.g. ``technology("cmos");`` - semantically equivalent to
    a simple attribute and treated as such here).
    """
    for stmt in group.body:
        if isinstance(stmt, Attr) and stmt.name == name:
            return stmt.value
        if (
            isinstance(stmt, ComplexAttr)
            and stmt.name == name
            and len(stmt.args) == 1
        ):
            return stmt.args[0]
    return None


def _find_groups(group: Group, name: str) -> list[Group]:
    return [s for s in group.body if isinstance(s, Group) and s.name == name]


def _cell_signature(cell: Group) -> dict[str, object]:
    """Extract the LLM-friendly summary fields for one cell."""
    area = _find_attr(cell, "area")
    leakage = _find_attr(cell, "cell_leakage_power")
    pins = _find_groups(cell, "pin")
    pg_pins = _find_groups(cell, "pg_pin")
    pin_directions: dict[str, str] = {}
    functions: dict[str, str] = {}
    for pin in pins:
        if not pin.args:
            continue
        pin_name = str(pin.args[0])
        direction = _find_attr(pin, "direction")
        if direction is not None:
            pin_directions[pin_name] = str(direction)
        func = _find_attr(pin, "function")
        if func is not None:
            functions[pin_name] = str(func)

    md: dict[str, object] = {
        "cell_name": cell.args[0] if cell.args else None,
        "pin_count": len(pins),
        "pg_pin_count": len(pg_pins),
        "pin_directions": pin_directions,
        "functions": functions,
    }
    if area is not None:
        md["area"] = float(area) if isinstance(area, (int, float)) else area
    if leakage is not None:
        md["cell_leakage_power"] = leakage
    return md


def _render_cell(cell: Group, sig: dict[str, object]) -> str:
    """Human-readable rendering used for embedding."""
    name = sig.get("cell_name") or "<unknown>"
    lines = [f"cell {name}"]
    if "area" in sig:
        lines.append(f"  area: {sig['area']}")
    if "cell_leakage_power" in sig:
        lines.append(f"  leakage_power: {sig['cell_leakage_power']}")
    dirs = sig.get("pin_directions") or {}
    if isinstance(dirs, dict) and dirs:
        lines.append("  pins:")
        for pin, direction in dirs.items():
            func = ""
            functions = sig.get("functions")
            if isinstance(functions, dict) and pin in functions:
                func = f"  function: {functions[pin]}"
            lines.append(f"    - {pin} ({direction}){func}")
    return "\n".join(lines)


def _library_metadata(lib: Group) -> dict[str, object]:
    md: dict[str, object] = {
        "library": lib.args[0] if lib.args else None,
    }
    for key in (
        "technology",
        "delay_model",
        "time_unit",
        "voltage_unit",
        "current_unit",
        "capacitive_load_unit",
        "leakage_power_unit",
        "pulling_resistance_unit",
        "nom_process",
        "nom_voltage",
        "nom_temperature",
        "default_operating_conditions",
    ):
        val = _find_attr(lib, key)
        if val is not None:
            md[key] = val
    # operating_conditions group(s) define PVT corners
    op_conds = []
    for oc in _find_groups(lib, "operating_conditions"):
        oc_meta: dict[str, object] = {
            "name": oc.args[0] if oc.args else None,
        }
        for k in ("process", "voltage", "temperature"):
            v = _find_attr(oc, k)
            if v is not None:
                oc_meta[k] = v
        op_conds.append(oc_meta)
    if op_conds:
        md["operating_conditions"] = op_conds
    cells = _find_groups(lib, "cell")
    md["cell_count"] = len(cells)
    md["total_pin_count"] = sum(len(_find_groups(c, "pin")) for c in cells)
    return md


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def _read(path: str | Path) -> str:
    p = Path(path)
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse_string(src: str) -> ParsedDocument:
    """Parse Liberty source text. Returns a :class:`ParsedDocument`."""
    toks = _tokenize(src)
    if not toks:
        raise LibertyParseError("empty input")
    parser = _Parser(toks)
    root = parser.parse_top()
    if root.name != "library":
        raise LibertyParseError(
            f"top-level group must be 'library' but got {root.name!r}"
        )

    lib_md = _library_metadata(root)
    chunks: list[Chunk] = []
    for cell in _find_groups(root, "cell"):
        sig = _cell_signature(cell)
        cell_name = str(sig.get("cell_name") or f"cell_{len(chunks)}")
        chunk_id = f"{lib_md.get('library')}::{cell_name}"
        chunks.append(
            Chunk(
                id=chunk_id,
                kind="cell",
                content=_render_cell(cell, sig),
                metadata=sig,
            )
        )

    header = f"liberty library: {lib_md.get('library')} ({lib_md.get('cell_count')} cells)"
    return ParsedDocument(
        content=header,
        metadata=lib_md,
        source_format="liberty",
        chunks=chunks,
        raw=root,
    )


def parse(path: str | Path) -> ParsedDocument:
    """Parse a Liberty file (``.lib`` or ``.lib.gz``)."""
    return parse_string(_read(path))
