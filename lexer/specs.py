from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenSpec:
    name: str
    pattern: str
    priority: int
    skip: bool = False


@dataclass(frozen=True)
class Token:
    type: str
    lexeme: str
    line: int
    column: int


@dataclass(frozen=True)
class LexError:
    message: str
    lexeme: str
    line: int
    column: int
