"""LEF (Library Exchange Format) parser.

LEF is a keyword-driven ASCII format that describes the *abstract* of a
cell library: technology layers, vias, sites, and per-MACRO pin/obstruction
geometry (without internal transistor topology). Statements end with ``;``;
named blocks end with ``END <name>``; nested ``PORT`` and ``OBS`` blocks
end with a bare ``END``. Line comments start with ``#``.

This parser produces a tree of :class:`LefBlock` and :class:`LefStmt`
nodes, then folds it into a :class:`~eda_parse.types.ParsedDocument` with
one :class:`Chunk` per ``MACRO``. Tech-LEFs (no MACROs) parse to an empty
chunk list with all metadata still extracted; cell-LEFs produce one chunk
per macro.
"""

from __future__ import annotations

import gzip
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from eda_parse.types import Chunk, ParsedDocument

# Block keywords that start a *named* block: ``KEYWORD name ... END name``
_NAMED_BLOCKS = {
    "MACRO",
    "LAYER",
    "VIA",
    "VIARULE",
    "SITE",
    "PIN",
    "NONDEFAULTRULE",
    "ARRAY",
}
# Block keywords that start an *unnamed* block: ``KEYWORD ... END [KEYWORD]``
# (END may or may not repeat the keyword; e.g. ``END UNITS`` vs bare ``END``.)
_UNNAMED_BLOCKS = {
    "UNITS",
    "PROPERTYDEFINITIONS",
    "OBS",
    "PORT",
    "BEGINEXT",
    "SPACING",
    # NOTE: SPACINGTABLE looks like a block but is actually a multi-line
    # *statement* ending with ``;`` (no END terminator). Leave it as a regular
    # simple statement.
}
_BLOCK_STARTERS = _NAMED_BLOCKS | _UNNAMED_BLOCKS
_AMBIGUOUS_BLOCK_STARTERS = {"SPACING"}
_SPACING_BLOCK_BODY_KEYWORDS = {"SAMENET"}


@dataclass
class LefStmt:
    """A simple ``KEYWORD args... ;`` statement."""

    keyword: str
    args: list[str] = field(default_factory=list)


@dataclass
class LefBlock:
    """A ``KEYWORD [name] body END [name]`` block."""

    keyword: str
    name: str | None = None
    args: list[str] = field(default_factory=list)
    body: list[LefBlock | LefStmt] = field(default_factory=list)


class LefParseError(ValueError):
    """Raised when a LEF file cannot be parsed."""


# ----------------------------------------------------------------------
# Tokenizer
# ----------------------------------------------------------------------


@dataclass
class _Tok:
    text: str
    line: int


def _tokenize(src: str) -> list[_Tok]:
    """Whitespace-separated tokens. ``;`` is its own token. ``#`` starts a
    line comment. Double-quoted strings (used for BUSBITCHARS etc.) are
    returned as a single token *with* their surrounding quotes preserved -
    consumers strip them if needed. Newlines are not tokens; LEF is not
    line-sensitive."""
    toks: list[_Tok] = []
    i = 0
    n = len(src)
    line = 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if c == "#":
            # comment to end of line
            j = src.find("\n", i)
            if j == -1:
                break
            i = j  # newline handled by next iter
            continue
        if c == ";":
            toks.append(_Tok(";", line))
            i += 1
            continue
        if c == '"':
            j = src.find('"', i + 1)
            if j == -1:
                raise LefParseError(f"unterminated string at line {line}")
            toks.append(_Tok(src[i : j + 1], line))
            line += src.count("\n", i, j + 1)
            i = j + 1
            continue
        # bareword: read until whitespace or ';' or '#'
        j = i
        while j < n and src[j] not in " \t\r\n;#":
            j += 1
        if j == i:
            raise LefParseError(f"empty token at line {line}, char {c!r}")
        toks.append(_Tok(src[i:j], line))
        i = j
    return toks


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------


class _Parser:
    def __init__(self, toks: list[_Tok]) -> None:
        self.toks = toks
        self.i = 0

    def _peek(self) -> _Tok | None:
        if self.i >= len(self.toks):
            return None
        return self.toks[self.i]

    def _eat(self) -> _Tok:
        tok = self._peek()
        if tok is None:
            raise LefParseError("unexpected end of input")
        self.i += 1
        return tok

    def parse_top(self) -> list[LefBlock | LefStmt]:
        body: list[LefBlock | LefStmt] = []
        while True:
            tok = self._peek()
            if tok is None:
                break
            if tok.text == "END" and self.i + 1 < len(self.toks) and self.toks[self.i + 1].text == "LIBRARY":
                # consume the optional file-final 'END LIBRARY'
                self.i += 2
                break
            body.append(self._parse_statement_or_block(end_names=None))
        return body

    def _parse_statement_or_block(self, end_names: set[str] | None) -> LefBlock | LefStmt:
        """Parse one top-of-current-scope item. ``end_names`` is the set of
        block names that would end the enclosing block; passed in so we can
        detect nested ``END <name>`` without consuming it.
        """
        kw_tok = self._eat()
        kw = kw_tok.text

        if kw in _BLOCK_STARTERS and not self._is_ambiguous_statement(kw):
            return self._parse_block(kw, kw_tok.line)

        return self._parse_simple_statement(kw, kw_tok.line)

    def _is_ambiguous_statement(self, kw: str) -> bool:
        """Return true when a keyword can be block or statement syntax.

        LEF uses top-level ``SPACING ... END SPACING`` blocks, but generated
        via rules also contain simple ``SPACING <x> BY <y> ;`` statements.
        """
        if kw not in _AMBIGUOUS_BLOCK_STARTERS:
            return False
        nxt = self._peek()
        if nxt is None:
            return False
        if kw == "SPACING":
            return nxt.text not in _SPACING_BLOCK_BODY_KEYWORDS
        return False

    def _parse_simple_statement(self, kw: str, line: int) -> LefStmt:
        # Simple ``KW args ;`` statement.
        args: list[str] = []
        while True:
            t = self._peek()
            if t is None:
                raise LefParseError(
                    f"unexpected EOF inside statement {kw!r} starting line {line}"
                )
            if t.text == ";":
                self.i += 1
                break
            self.i += 1
            args.append(t.text)
        return LefStmt(keyword=kw, args=args)

    def _parse_block(self, kw: str, line: int) -> LefBlock:
        name: str | None = None
        args: list[str] = []
        # Named blocks: the next token is the block name (a bareword).
        if kw in _NAMED_BLOCKS:
            name_tok = self._eat()
            name = name_tok.text
            # Some blocks carry additional flags after the name before the body
            # (e.g. ``VIARULE foo GENERATE``); collect any further tokens that
            # are not block keywords and not punctuation, up to either ``;``
            # (no body) or the first known keyword/structural token.
            while True:
                t = self._peek()
                if t is None:
                    raise LefParseError(f"unexpected EOF in {kw} {name} header at line {line}")
                if t.text == ";":
                    # Some LEFs use a one-liner form like ``LAYER foo ;`` -
                    # treat as a degenerate empty block.
                    self.i += 1
                    return LefBlock(keyword=kw, name=name, args=args, body=[])
                # If the next token starts a new statement inside this block,
                # stop header collection. Heuristic: any uppercase keyword that
                # is plausibly a body statement.
                if t.text.isupper() or t.text in _BLOCK_STARTERS:
                    break
                self.i += 1
                args.append(t.text)

        body: list[LefBlock | LefStmt] = []
        while True:
            t = self._peek()
            if t is None:
                raise LefParseError(
                    f"unexpected EOF in {kw} block starting line {line}"
                )
            if t.text == "END":
                # Possible terminators:
                #   END <name>       - named block terminator
                #   END <keyword>    - unnamed block terminator (e.g. END UNITS)
                #   END              - bare END (e.g. PORT, OBS)
                nxt = self.toks[self.i + 1] if self.i + 1 < len(self.toks) else None
                if nxt is None:
                    raise LefParseError(f"END at EOF in {kw} block")
                if name is not None and nxt.text == name:
                    self.i += 2
                    return LefBlock(keyword=kw, name=name, args=args, body=body)
                if kw in _UNNAMED_BLOCKS and nxt.text == kw and nxt.line == t.line:
                    self.i += 2
                    return LefBlock(keyword=kw, name=name, args=args, body=body)
                if kw in _UNNAMED_BLOCKS:
                    # bare END terminates PORT / OBS
                    self.i += 1
                    return LefBlock(keyword=kw, name=name, args=args, body=body)
                # Otherwise: bare END terminates a named block too (some
                # writers omit the name).
                self.i += 1
                return LefBlock(keyword=kw, name=name, args=args, body=body)
            if kw == "PROPERTYDEFINITIONS":
                prop_kw = self._eat()
                body.append(self._parse_simple_statement(prop_kw.text, prop_kw.line))
                continue
            body.append(self._parse_statement_or_block(end_names=None))


# ----------------------------------------------------------------------
# AST -> ParsedDocument
# ----------------------------------------------------------------------


def _block_first_stmt(block: LefBlock, keyword: str) -> LefStmt | None:
    for s in block.body:
        if isinstance(s, LefStmt) and s.keyword == keyword:
            return s
    return None


def _macro_metadata(macro: LefBlock) -> dict[str, object]:
    md: dict[str, object] = {"macro_name": macro.name}

    cls = _block_first_stmt(macro, "CLASS")
    if cls:
        md["class"] = " ".join(cls.args)

    size = _block_first_stmt(macro, "SIZE")
    if size and len(size.args) >= 3:
        # SIZE <w> BY <h>
        try:
            md["width"] = float(size.args[0])
            md["height"] = float(size.args[2])
        except ValueError:
            pass

    origin = _block_first_stmt(macro, "ORIGIN")
    if origin and len(origin.args) >= 2:
        with suppress(ValueError):
            md["origin"] = [float(origin.args[0]), float(origin.args[1])]

    sym = _block_first_stmt(macro, "SYMMETRY")
    if sym:
        md["symmetry"] = list(sym.args)

    site = _block_first_stmt(macro, "SITE")
    if site:
        md["site"] = site.args[0] if site.args else None

    foreign = _block_first_stmt(macro, "FOREIGN")
    if foreign and foreign.args:
        md["foreign"] = foreign.args[0]

    pins: list[dict[str, object]] = []
    for s in macro.body:
        if isinstance(s, LefBlock) and s.keyword == "PIN":
            pin_md: dict[str, object] = {"name": s.name}
            d = _block_first_stmt(s, "DIRECTION")
            if d and d.args:
                pin_md["direction"] = d.args[0]
            u = _block_first_stmt(s, "USE")
            if u and u.args:
                pin_md["use"] = u.args[0]
            shape = _block_first_stmt(s, "SHAPE")
            if shape and shape.args:
                pin_md["shape"] = shape.args[0]
            pins.append(pin_md)
    md["pins"] = pins
    md["pin_count"] = len(pins)
    md["has_obs"] = any(
        isinstance(s, LefBlock) and s.keyword == "OBS" for s in macro.body
    )
    return md


def _render_macro(md: dict[str, object]) -> str:
    name = md.get("macro_name") or "<unknown>"
    lines = [f"macro {name}"]
    if "class" in md:
        lines.append(f"  class: {md['class']}")
    if "width" in md and "height" in md:
        lines.append(f"  size: {md['width']} x {md['height']}")
    if "symmetry" in md:
        sym = md["symmetry"]
        if isinstance(sym, list):
            lines.append(f"  symmetry: {' '.join(sym)}")
    if "site" in md:
        lines.append(f"  site: {md['site']}")
    pins_obj = md.get("pins")
    if isinstance(pins_obj, list) and pins_obj:
        lines.append("  pins:")
        for p in pins_obj:
            if isinstance(p, dict):
                direction = p.get("direction", "?")
                use = p.get("use", "")
                use_suffix = f" [{use}]" if use else ""
                lines.append(f"    - {p.get('name')} ({direction}){use_suffix}")
    if md.get("has_obs"):
        lines.append("  has obstructions")
    return "\n".join(lines)


def _toplevel_metadata(top: list[LefBlock | LefStmt]) -> dict[str, object]:
    md: dict[str, object] = {}
    for s in top:
        if isinstance(s, LefStmt):
            if s.keyword == "VERSION" and s.args:
                md["version"] = s.args[0]
            elif s.keyword == "BUSBITCHARS" and s.args:
                md["busbitchars"] = s.args[0].strip('"')
            elif s.keyword == "DIVIDERCHAR" and s.args:
                md["dividerchar"] = s.args[0].strip('"')
            elif s.keyword == "MANUFACTURINGGRID" and s.args:
                with suppress(ValueError):
                    md["manufacturing_grid"] = float(s.args[0])
        elif isinstance(s, LefBlock) and s.keyword == "UNITS":
            units: dict[str, str] = {}
            for u in s.body:
                if isinstance(u, LefStmt):
                    units[u.keyword.lower()] = " ".join(u.args)
            md["units"] = units

    layers = [s for s in top if isinstance(s, LefBlock) and s.keyword == "LAYER"]
    sites = [s for s in top if isinstance(s, LefBlock) and s.keyword == "SITE"]
    vias = [s for s in top if isinstance(s, LefBlock) and s.keyword == "VIA"]
    viarules = [s for s in top if isinstance(s, LefBlock) and s.keyword == "VIARULE"]
    macros = [s for s in top if isinstance(s, LefBlock) and s.keyword == "MACRO"]

    md["layer_count"] = len(layers)
    md["layer_names"] = [b.name for b in layers if b.name]
    md["site_count"] = len(sites)
    md["via_count"] = len(vias)
    md["viarule_count"] = len(viarules)
    md["macro_count"] = len(macros)

    has_layers = len(layers) > 0
    has_macros = len(macros) > 0
    if has_macros and not has_layers:
        kind = "cell"
    elif has_layers and not has_macros:
        kind = "tech"
    elif has_layers and has_macros:
        kind = "merged"
    else:
        kind = "unknown"
    md["lef_kind"] = kind
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
    """Parse LEF source text."""
    toks = _tokenize(src)
    if not toks:
        raise LefParseError("empty input")
    parser = _Parser(toks)
    top = parser.parse_top()

    md = _toplevel_metadata(top)
    chunks: list[Chunk] = []
    for blk in top:
        if isinstance(blk, LefBlock) and blk.keyword == "MACRO":
            macro_md = _macro_metadata(blk)
            macro_name = blk.name or f"macro_{len(chunks)}"
            chunks.append(
                Chunk(
                    id=f"lef::{macro_name}",
                    kind="macro",
                    content=_render_macro(macro_md),
                    metadata=macro_md,
                )
            )

    header = (
        f"lef {md.get('lef_kind')} file - "
        f"{md.get('layer_count')} layers, "
        f"{md.get('macro_count')} macros"
    )
    return ParsedDocument(
        content=header,
        metadata=md,
        source_format="lef",
        chunks=chunks,
        raw=top,
    )


def parse(path: str | Path) -> ParsedDocument:
    """Parse a LEF file (``.lef``, ``.tlef``, or gzipped variants)."""
    return parse_string(_read(path))
