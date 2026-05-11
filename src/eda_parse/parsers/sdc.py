"""SDC (Synopsys Design Constraints) parser.

SDC is a TCL-derived constraint format used by every digital synthesis,
placement, and timing tool. Spec: Synopsys SDC reference (the format is
open even though some tool flags are proprietary). The grammar is TCL,
but the *usage* of SDC is a small, well-known set of commands —
``create_clock``, ``set_input_delay``, ``set_output_delay``,
``set_false_path``, ``set_multicycle_path``, ``set_clock_groups`` and a
handful more.

This module implements a hand-rolled TCL-ish tokenizer (handles
brace-lists ``{a b c}``, bracket command-substitution ``[get_ports x]``,
``$var`` references, ``#`` comments, ``\\``-newline continuation, and
both newline and ``;`` as statement terminators) plus a small command
dispatcher that recognizes the SDC verbs and folds each into a
:class:`~eda_parse.types.Chunk`. ``set`` assignments are tracked and
``$var`` references in subsequent commands are resolved inline so the
parsed metadata carries final values, not unresolved strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eda_parse.types import Chunk, ParsedDocument


class SDCParseError(ValueError):
    """Raised when an SDC file cannot be tokenized or parsed."""


# ----------------------------------------------------------------------
# Tokenizer
# ----------------------------------------------------------------------


@dataclass
class _Tok:
    kind: str  # 'word', 'string', 'lbrace', 'rbrace', 'lbracket', 'rbracket', 'eol'
    text: str
    line: int


def _tokenize(src: str) -> list[_Tok]:
    """Tokenize TCL-ish source.

    Newlines and ``;`` are statement terminators (emitted as ``eol``
    tokens). ``\\``-newline folds two source lines into one statement.
    Brace and bracket pairs are *not* matched here — they are individual
    tokens; matching happens during arg parsing.
    """
    toks: list[_Tok] = []
    i = 0
    n = len(src)
    line = 1
    while i < n:
        c = src[i]
        if c == "\n":
            toks.append(_Tok("eol", "\\n", line))
            line += 1
            i += 1
            continue
        if c == "\r":
            i += 1
            continue
        if c == "\\" and i + 1 < n and src[i + 1] == "\n":
            line += 1
            i += 2
            continue
        if c in " \t":
            i += 1
            continue
        if c == ";":
            toks.append(_Tok("eol", ";", line))
            i += 1
            continue
        if c == "#":
            j = src.find("\n", i)
            if j == -1:
                break
            i = j  # newline handled by next iter
            continue
        if c == "{":
            toks.append(_Tok("lbrace", "{", line))
            i += 1
            continue
        if c == "}":
            toks.append(_Tok("rbrace", "}", line))
            i += 1
            continue
        if c == "[":
            toks.append(_Tok("lbracket", "[", line))
            i += 1
            continue
        if c == "]":
            toks.append(_Tok("rbracket", "]", line))
            i += 1
            continue
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
                raise SDCParseError(
                    f"unterminated string starting at line {start_line}"
                )
            toks.append(_Tok("string", "".join(buf), start_line))
            i = j + 1
            continue
        # bareword
        j = i
        while j < n and src[j] not in " \t\r\n;{}[]\"#":
            j += 1
        if j == i:
            raise SDCParseError(f"unexpected character {c!r} at line {line}")
        toks.append(_Tok("word", src[i:j], line))
        i = j
    return toks


# ----------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------


def _read_brace_list(toks: list[_Tok], i: int) -> tuple[str, int]:
    """Read tokens until the matching ``}``, return as a single space-joined
    string preserving nesting at the textual level. Assumes ``toks[i]`` is
    the first token *after* ``{``."""
    depth = 1
    parts: list[str] = []
    while i < len(toks):
        t = toks[i]
        if t.kind == "lbrace":
            depth += 1
            parts.append("{")
            i += 1
            continue
        if t.kind == "rbrace":
            depth -= 1
            if depth == 0:
                return " ".join(parts), i + 1
            parts.append("}")
            i += 1
            continue
        if t.kind == "eol":
            # newlines inside braces are whitespace
            i += 1
            continue
        parts.append(t.text)
        i += 1
    raise SDCParseError("unterminated brace list")


def _read_bracket_expr(toks: list[_Tok], i: int) -> tuple[str, int]:
    """Read tokens until the matching ``]``. Same conventions as
    ``_read_brace_list``. Returns the textual command string so consumers
    can introspect (e.g. ``"get_ports clk"``)."""
    depth = 1
    parts: list[str] = []
    while i < len(toks):
        t = toks[i]
        if t.kind == "lbracket":
            depth += 1
            parts.append("[")
            i += 1
            continue
        if t.kind == "rbracket":
            depth -= 1
            if depth == 0:
                return " ".join(parts), i + 1
            parts.append("]")
            i += 1
            continue
        if t.kind == "eol":
            i += 1
            continue
        parts.append(t.text)
        i += 1
    raise SDCParseError("unterminated bracket expression")


def _resolve_var(text: str, variables: dict[str, str]) -> str:
    """Resolve a ``$var`` reference; if the value is unknown leave it as-is."""
    if not text.startswith("$"):
        return text
    name = text[1:]
    return variables.get(name, text)


def _read_arg(
    toks: list[_Tok], i: int, variables: dict[str, str]
) -> tuple[str, int]:
    """Read a single argument starting at ``toks[i]``. Returns the textual
    value (with any ``$var`` references resolved if possible) and the new
    cursor."""
    t = toks[i]
    if t.kind == "lbrace":
        text, i2 = _read_brace_list(toks, i + 1)
        return text, i2
    if t.kind == "lbracket":
        text, i2 = _read_bracket_expr(toks, i + 1)
        return f"[{text}]", i2
    if t.kind == "string":
        return t.text, i + 1
    if t.kind == "word":
        return _resolve_var(t.text, variables), i + 1
    raise SDCParseError(
        f"unexpected token {t.kind} {t.text!r} at line {t.line}"
    )


# ----------------------------------------------------------------------
# Statement parsing
# ----------------------------------------------------------------------


@dataclass
class _Stmt:
    cmd: str
    args: list[str] = field(default_factory=list)
    flags: dict[str, str | bool | list[str]] = field(default_factory=dict)
    line: int = 0


_KNOWN_FLAG_NAMES = {
    # value-carrying flags shared across many SDC commands
    "-name", "-period", "-waveform", "-source", "-divide_by", "-multiply_by",
    "-edges", "-edge_shift", "-master_clock", "-clock", "-clocks", "-from",
    "-to", "-through", "-rise_from", "-fall_from", "-rise_to", "-fall_to",
    "-group", "-setup", "-hold", "-min", "-max",
    # set_input_delay / set_output_delay
    "-clock_fall", "-network_latency_included", "-source_latency_included",
    "-reference_pin", "-level_sensitive",
    # set_clock_groups
    "-physically_exclusive", "-logically_exclusive",
}
_BOOLEAN_FLAG_NAMES = {
    "-add_clock", "-asynchronous", "-physically_exclusive",
    "-logically_exclusive", "-add_delay", "-no_propagated_clock",
    "-rise", "-fall", "-setup", "-hold", "-min", "-max",
    "-start", "-end",
}


def _parse_stmt(
    toks: list[_Tok], i: int, variables: dict[str, str]
) -> tuple[_Stmt | None, int]:
    """Parse one statement starting at ``toks[i]``. Returns ``(stmt, next_i)``
    or ``(None, next_i)`` if the cursor lands on an EOL (empty statement).
    """
    while i < len(toks) and toks[i].kind == "eol":
        i += 1
    if i >= len(toks):
        return None, i
    cmd_tok = toks[i]
    if cmd_tok.kind != "word":
        raise SDCParseError(
            f"expected command at line {cmd_tok.line}, got {cmd_tok.kind} {cmd_tok.text!r}"
        )
    stmt = _Stmt(cmd=cmd_tok.text, line=cmd_tok.line)
    i += 1
    while i < len(toks):
        t = toks[i]
        if t.kind == "eol":
            i += 1
            break
        if t.kind == "word" and t.text.startswith("-"):
            flag = t.text
            # Group flags can repeat (-group {a b} -group {c d}); collect them.
            is_value_flag = flag in _KNOWN_FLAG_NAMES or flag == "-group"
            is_bool_flag = flag in _BOOLEAN_FLAG_NAMES and not is_value_flag
            i += 1
            if is_bool_flag:
                stmt.flags[flag] = True
                continue
            if is_value_flag and i < len(toks) and toks[i].kind != "eol":
                value, i = _read_arg(toks, i, variables)
                # special-case repeated -group
                if flag == "-group":
                    existing = stmt.flags.get("-group")
                    if isinstance(existing, list):
                        existing.append(value)
                    elif existing is None:
                        stmt.flags["-group"] = [value]
                    elif isinstance(existing, str):
                        stmt.flags["-group"] = [existing, value]
                else:
                    stmt.flags[flag] = value
                continue
            # Unknown flag — record as boolean to avoid swallowing a positional
            stmt.flags[flag] = True
            continue
        value, i = _read_arg(toks, i, variables)
        stmt.args.append(value)
    return stmt, i


# ----------------------------------------------------------------------
# AST → ParsedDocument
# ----------------------------------------------------------------------


def _chunk_for(stmt: _Stmt, chunk_index: int) -> Chunk | None:
    """Turn one statement into a Chunk if it's a recognized SDC constraint.

    Returns ``None`` for commands that aren't constraint-emitting (e.g.
    ``set``, ``current_design``) — those still update document-level
    metadata but don't produce chunks.
    """
    md: dict[str, Any] = {"line": stmt.line, "command": stmt.cmd}
    content_lines: list[str] = [stmt.cmd]

    if stmt.cmd == "create_clock":
        period = stmt.flags.get("-period")
        name = stmt.flags.get("-name")
        waveform = stmt.flags.get("-waveform")
        ports: str | bool | list[str] | None = (
            stmt.args[0] if stmt.args else None
        )
        if ports is None and "-clock" in stmt.flags:
            ports = stmt.flags["-clock"]
        if name is None and isinstance(ports, str):
            # If no -name given, the clock is named by its source port.
            # Don't try too hard to compute that; just record the port.
            pass
        if isinstance(period, str):
            try:
                md["period"] = float(period)
            except ValueError:
                md["period"] = period
        if name is not None:
            md["name"] = name
        if waveform is not None:
            md["waveform"] = waveform
        if ports is not None:
            md["ports"] = ports
        kind = "clock"
        content_lines.append(f"  period: {md.get('period')}")
        if name is not None:
            content_lines.append(f"  name: {name}")
        if ports is not None:
            content_lines.append(f"  applies to: {ports}")

    elif stmt.cmd == "create_generated_clock":
        kind = "generated_clock"
        for k in ("-name", "-source", "-divide_by", "-multiply_by", "-master_clock"):
            v = stmt.flags.get(k)
            if v is not None:
                md[k.lstrip("-")] = v
        if stmt.args:
            md["pin"] = stmt.args[0]
        content_lines.append(f"  source: {md.get('source')}  divide_by: {md.get('divide_by')}")

    elif stmt.cmd == "set_input_delay":
        kind = "input_delay"
        if stmt.args:
            try:
                md["delay"] = float(stmt.args[0])
            except ValueError:
                md["delay"] = stmt.args[0]
        if len(stmt.args) >= 2:
            md["ports"] = stmt.args[1]
        if "-clock" in stmt.flags:
            md["clock"] = stmt.flags["-clock"]
        for boolflag in ("-min", "-max", "-clock_fall"):
            if stmt.flags.get(boolflag):
                md[boolflag.lstrip("-")] = True
        content_lines.append(f"  delay: {md.get('delay')}  clock: {md.get('clock')}  ports: {md.get('ports')}")

    elif stmt.cmd == "set_output_delay":
        kind = "output_delay"
        if stmt.args:
            try:
                md["delay"] = float(stmt.args[0])
            except ValueError:
                md["delay"] = stmt.args[0]
        if len(stmt.args) >= 2:
            md["ports"] = stmt.args[1]
        if "-clock" in stmt.flags:
            md["clock"] = stmt.flags["-clock"]
        for boolflag in ("-min", "-max", "-clock_fall"):
            if stmt.flags.get(boolflag):
                md[boolflag.lstrip("-")] = True
        content_lines.append(f"  delay: {md.get('delay')}  clock: {md.get('clock')}  ports: {md.get('ports')}")

    elif stmt.cmd == "set_input_transition":
        kind = "input_transition"
        if stmt.args:
            try:
                md["transition"] = float(stmt.args[0])
            except ValueError:
                md["transition"] = stmt.args[0]
        if len(stmt.args) >= 2:
            md["ports"] = stmt.args[1]
        content_lines.append(f"  transition: {md.get('transition')}  ports: {md.get('ports')}")

    elif stmt.cmd == "set_load":
        kind = "load"
        if stmt.args:
            try:
                md["load"] = float(stmt.args[0])
            except ValueError:
                md["load"] = stmt.args[0]
        if len(stmt.args) >= 2:
            md["ports"] = stmt.args[1]
        content_lines.append(f"  load: {md.get('load')}  ports: {md.get('ports')}")

    elif stmt.cmd == "set_false_path":
        kind = "false_path"
        for k in ("-from", "-to", "-through"):
            v = stmt.flags.get(k)
            if v is not None:
                md[k.lstrip("-")] = v
        for k in ("-setup", "-hold"):
            if stmt.flags.get(k):
                md[k.lstrip("-")] = True
        content_lines.append(f"  from: {md.get('from')}  to: {md.get('to')}")

    elif stmt.cmd == "set_multicycle_path":
        kind = "multicycle_path"
        if stmt.args:
            try:
                md["cycles"] = int(stmt.args[0])
            except ValueError:
                md["cycles"] = stmt.args[0]
        for k in ("-from", "-to", "-through"):
            v = stmt.flags.get(k)
            if v is not None:
                md[k.lstrip("-")] = v
        for k in ("-setup", "-hold", "-start", "-end"):
            if stmt.flags.get(k):
                md[k.lstrip("-")] = True
        content_lines.append(f"  cycles: {md.get('cycles')}  from: {md.get('from')}  to: {md.get('to')}")

    elif stmt.cmd == "set_clock_groups":
        kind = "clock_groups"
        groups = stmt.flags.get("-group")
        if isinstance(groups, list):
            md["groups"] = groups
        elif isinstance(groups, str):
            md["groups"] = [groups]
        for boolflag in ("-asynchronous", "-physically_exclusive", "-logically_exclusive"):
            if stmt.flags.get(boolflag):
                md[boolflag.lstrip("-")] = True
        content_lines.append(f"  groups: {md.get('groups')}")

    else:
        return None

    return Chunk(
        id=f"sdc::{stmt.cmd}::{chunk_index}",
        kind=kind,
        content="\n".join(content_lines),
        metadata=md,
    )


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def parse_string(src: str) -> ParsedDocument:
    """Parse SDC source text."""
    toks = _tokenize(src)
    variables: dict[str, str] = {}
    chunks: list[Chunk] = []
    statements: list[_Stmt] = []
    design: str | None = None
    i = 0
    chunk_index = 0
    while i < len(toks):
        stmt, i = _parse_stmt(toks, i, variables)
        if stmt is None:
            continue
        statements.append(stmt)
        # Variable assignment: ``set <name> <value>`` — track for future
        # ``$var`` substitution. The value may itself be a bracket expression
        # like ``[expr $period * 0.2]`` — we don't evaluate those; we record
        # them as-is and downstream commands that try to resolve ``$delay``
        # will get the textual ``[expr ...]`` placeholder, which is fine for
        # static metadata extraction.
        if stmt.cmd == "set" and len(stmt.args) >= 2:
            variables[stmt.args[0]] = stmt.args[1]
            continue
        if stmt.cmd == "current_design" and stmt.args:
            design = stmt.args[0]
            continue
        chunk = _chunk_for(stmt, chunk_index)
        if chunk is not None:
            chunks.append(chunk)
            chunk_index += 1

    md: dict[str, Any] = {
        "design": design,
        "variables": variables,
        "statement_count": len(statements),
        "clock_count": sum(1 for c in chunks if c.kind == "clock"),
        "generated_clock_count": sum(1 for c in chunks if c.kind == "generated_clock"),
        "input_delay_count": sum(1 for c in chunks if c.kind == "input_delay"),
        "output_delay_count": sum(1 for c in chunks if c.kind == "output_delay"),
        "input_transition_count": sum(1 for c in chunks if c.kind == "input_transition"),
        "load_count": sum(1 for c in chunks if c.kind == "load"),
        "false_path_count": sum(1 for c in chunks if c.kind == "false_path"),
        "multicycle_path_count": sum(1 for c in chunks if c.kind == "multicycle_path"),
        "clock_groups_count": sum(1 for c in chunks if c.kind == "clock_groups"),
    }
    header = (
        f"sdc constraints — {md['clock_count']} clocks, "
        f"{md['input_delay_count']} input_delay, "
        f"{md['output_delay_count']} output_delay, "
        f"{md['false_path_count']} false_path, "
        f"{md['multicycle_path_count']} multicycle_path"
    )
    return ParsedDocument(
        content=header,
        metadata=md,
        source_format="sdc",
        chunks=chunks,
        raw=statements,
    )


def parse(path: str | Path) -> ParsedDocument:
    """Parse an SDC file."""
    p = Path(path)
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        return parse_string(fh.read())
