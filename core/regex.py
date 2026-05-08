from __future__ import annotations

from dataclasses import dataclass

DEFAULT_CLASS_UNIVERSE = (
    {chr(code) for code in range(32, 127)}
    | {"\t", "\r", "\n"}
)
CONCAT = "."
UNARY_OPERATORS = {"*", "+", "?"}
BINARY_PRECEDENCE = {"|": 1, CONCAT: 2}
META_CHARACTERS = set(r"\|*+?()[]")


@dataclass(frozen=True)
class RegexAtom:
    symbols: frozenset[str]


RegexIR = list[str | RegexAtom]


class RegexParser:
    """Parses a simplified regex into postfix form for Thompson construction."""

    @classmethod
    def parse(cls, pattern: str) -> RegexIR:
        tokens = cls._tokenize(pattern)
        tokens = cls._insert_concat(tokens)
        return cls._to_postfix(tokens)

    @classmethod
    def escape_literal(cls, text: str) -> str:
        if len(text) != 1:
            raise ValueError("escape_literal expects a single character")
        if text in META_CHARACTERS or text == ".":
            return "\\" + text
        return text

    @classmethod
    def literal_pattern(cls, text: str) -> str:
        return "".join(cls.escape_literal(char) for char in text)

    @classmethod
    def char_class(cls, chars: set[str] | list[str] | tuple[str, ...] | str) -> str:
        if isinstance(chars, str):
            iterable = list(chars)
        else:
            iterable = list(chars)
        if not iterable:
            raise ValueError("character class cannot be empty")

        def encode(char: str) -> str:
            mapping = {"\n": r"\n", "\t": r"\t", "\r": r"\r"}
            if char in mapping:
                return mapping[char]
            if char in {"\\", "]", "-", "^"}:
                return "\\" + char
            return char

        body = "".join(encode(char) for char in sorted(set(iterable)))
        return f"[{body}]"

    @classmethod
    def _tokenize(cls, pattern: str) -> RegexIR:
        tokens: RegexIR = []
        index = 0
        while index < len(pattern):
            char = pattern[index]
            if char == "\\":
                if index + 1 >= len(pattern):
                    raise ValueError("dangling escape in regex pattern")
                tokens.append(RegexAtom(frozenset({cls._decode_escape(pattern[index + 1])})))
                index += 2
                continue
            if char == "[":
                chars, index = cls._parse_char_class(pattern, index + 1)
                tokens.append(RegexAtom(frozenset(chars)))
                continue
            if char in {"(", ")", "|", "*", "+", "?"}:
                tokens.append(char)
                index += 1
                continue
            tokens.append(RegexAtom(frozenset({char})))
            index += 1
        return tokens

    @classmethod
    def _parse_char_class(cls, pattern: str, index: int) -> tuple[set[str], int]:
        if index >= len(pattern):
            raise ValueError("unterminated character class")

        negate = False
        if pattern[index] == "^":
            negate = True
            index += 1

        chars: list[str] = []
        while index < len(pattern):
            char = pattern[index]
            if char == "]" and chars:
                result = set(chars)
                if negate:
                    result = set(DEFAULT_CLASS_UNIVERSE) - result
                return result, index + 1
            if char == "\\":
                if index + 1 >= len(pattern):
                    raise ValueError("unterminated escape inside character class")
                chars.append(cls._decode_escape(pattern[index + 1]))
                index += 2
                continue
            if (
                index + 2 < len(pattern)
                and pattern[index + 1] == "-"
                and pattern[index + 2] != "]"
            ):
                start = ord(char)
                end = ord(pattern[index + 2])
                if start > end:
                    raise ValueError("invalid range inside character class")
                chars.extend(chr(code) for code in range(start, end + 1))
                index += 3
                continue
            chars.append(char)
            index += 1
        raise ValueError("unterminated character class")

    @classmethod
    def _decode_escape(cls, char: str) -> str:
        mapping = {"n": "\n", "t": "\t", "r": "\r"}
        return mapping.get(char, char)

    @classmethod
    def _insert_concat(cls, tokens: RegexIR) -> RegexIR:
        if not tokens:
            raise ValueError("regex pattern cannot be empty")

        result: RegexIR = []
        for index, token in enumerate(tokens):
            if index > 0 and cls._needs_concat(tokens[index - 1], token):
                result.append(CONCAT)
            result.append(token)
        return result

    @classmethod
    def _needs_concat(cls, left: str | RegexAtom, right: str | RegexAtom) -> bool:
        return cls._is_concat_left(left) and cls._is_concat_right(right)

    @classmethod
    def _is_concat_left(cls, token: str | RegexAtom) -> bool:
        return isinstance(token, RegexAtom) or token == ")" or token in UNARY_OPERATORS

    @classmethod
    def _is_concat_right(cls, token: str | RegexAtom) -> bool:
        return isinstance(token, RegexAtom) or token == "("

    @classmethod
    def _to_postfix(cls, tokens: RegexIR) -> RegexIR:
        output: RegexIR = []
        operators: list[str] = []

        for token in tokens:
            if isinstance(token, RegexAtom):
                output.append(token)
            elif token in UNARY_OPERATORS:
                output.append(token)
            elif token == "(":
                operators.append(token)
            elif token == ")":
                while operators and operators[-1] != "(":
                    output.append(operators.pop())
                if not operators:
                    raise ValueError("mismatched closing parenthesis")
                operators.pop()
            else:
                while (
                    operators
                    and operators[-1] != "("
                    and BINARY_PRECEDENCE[operators[-1]] >= BINARY_PRECEDENCE[token]
                ):
                    output.append(operators.pop())
                operators.append(token)

        while operators:
            top = operators.pop()
            if top == "(":
                raise ValueError("mismatched opening parenthesis")
            output.append(top)
        return output
