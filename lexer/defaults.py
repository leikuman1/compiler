from __future__ import annotations

import string

from compiler_project.core.regex import RegexParser

from .compiler import CompiledLexer, LexerCompiler
from .specs import TokenSpec


def _literal(text: str) -> str:
    return RegexParser.literal_pattern(text)


def _char_class(chars: str | set[str]) -> str:
    return RegexParser.char_class(chars)


def _keyword(name: str, priority: int) -> TokenSpec:
    return TokenSpec(name=f"KW_{name.upper()}", pattern=_literal(name), priority=priority)


def _operator(name: str, token: str, priority: int) -> TokenSpec:
    return TokenSpec(name=name, pattern=_literal(token), priority=priority)


def _delim(name: str, token: str, priority: int) -> TokenSpec:
    return TokenSpec(name=name, pattern=_literal(token), priority=priority)


def default_token_specs() -> list[TokenSpec]:
    ident_start = _char_class(string.ascii_letters + "_")
    ident_continue = _char_class(string.ascii_letters + string.digits + "_")
    digits = _char_class(string.digits)
    whitespace_chars = _char_class(" \t\r\n")
    visible_ascii = {chr(code) for code in range(32, 127)}
    line_comment_body = _char_class((visible_ascii | {"\t"}) - {"\n", "\r"})
    block_chars = visible_ascii | {"\t", "\r", "\n"}
    not_star = _char_class(block_chars - {"*"})
    not_star_or_slash = _char_class(block_chars - {"*", "/"})
    star = _char_class({"*"})

    specs = [
        _keyword("int", 1),
        _keyword("char", 1),
        _keyword("void", 1),
        _keyword("if", 1),
        _keyword("else", 1),
        _keyword("while", 1),
        _keyword("for", 1),
        _keyword("return", 1),
        TokenSpec(
            name="LINE_COMMENT",
            pattern=_literal("//") + line_comment_body + "*",
            priority=2,
            skip=True,
        ),
        TokenSpec(
            name="BLOCK_COMMENT",
            pattern=_literal("/*") + "(" + not_star + "|" + star + "+" + not_star_or_slash + ")*" + star + "+" + _literal("/"),
            priority=2,
            skip=True,
        ),
        TokenSpec(name="WHITESPACE", pattern=whitespace_chars + "+", priority=3, skip=True),
        _operator("OP_INC", "++", 4),
        _operator("OP_DEC", "--", 4),
        _operator("OP_EQ", "==", 4),
        _operator("OP_NE", "!=", 4),
        _operator("OP_LE", "<=", 4),
        _operator("OP_GE", ">=", 4),
        _operator("OP_AND", "&&", 4),
        _operator("OP_OR", "||", 4),
        _operator("OP_ASSIGN", "=", 5),
        _operator("OP_LT", "<", 5),
        _operator("OP_GT", ">", 5),
        _operator("OP_PLUS", "+", 5),
        _operator("OP_MINUS", "-", 5),
        _operator("OP_MUL", "*", 5),
        _operator("OP_DIV", "/", 5),
        _operator("OP_MOD", "%", 5),
        _operator("OP_NOT", "!", 5),
        _delim("LPAREN", "(", 6),
        _delim("RPAREN", ")", 6),
        _delim("LBRACE", "{", 6),
        _delim("RBRACE", "}", 6),
        _delim("LBRACKET", "[", 6),
        _delim("RBRACKET", "]", 6),
        _delim("SEMICOLON", ";", 6),
        _delim("COMMA", ",", 6),
        TokenSpec(name="FLOAT", pattern=digits + "+" + _literal(".") + digits + "+", priority=7),
        TokenSpec(name="INTEGER", pattern=digits + "+", priority=8),
        TokenSpec(name="IDENTIFIER", pattern=ident_start + ident_continue + "*", priority=9),
    ]
    return specs


def build_default_lexer() -> CompiledLexer:
    return LexerCompiler.compile(default_token_specs())
