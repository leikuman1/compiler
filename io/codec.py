from __future__ import annotations

from pathlib import Path

from compiler_project.core.models import DFA, EPSILON, NFA


class AutomataCodec:
    """Reads and writes automata files compatible with coursework examples."""

    ENCODINGS = ("utf-8-sig", "utf-8", "gbk")

    @classmethod
    def read_text_file(cls, path: str | Path) -> str:
        last_error: Exception | None = None
        for encoding in cls.ENCODINGS:
            try:
                return Path(path).read_text(encoding=encoding)
            except UnicodeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise ValueError(f"unable to read file: {path}")

    @classmethod
    def load_nfa(cls, path: str | Path) -> NFA:
        text = cls.read_text_file(path)
        return cls.parse_nfa(text)

    @classmethod
    def load_dfa(cls, path: str | Path) -> DFA:
        text = cls.read_text_file(path)
        return cls.parse_dfa(text)

    @classmethod
    def save_nfa(cls, nfa: NFA, path: str | Path) -> None:
        Path(path).write_text(cls.format_nfa(nfa), encoding="utf-8-sig")

    @classmethod
    def save_dfa(cls, dfa: DFA, path: str | Path) -> None:
        Path(path).write_text(cls.format_dfa(dfa), encoding="utf-8-sig")

    @classmethod
    def parse_nfa(cls, text: str) -> NFA:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 3:
            raise ValueError("NFA file is incomplete")

        start_state = cls._parse_single_state(lines[0])
        accept_states = cls._parse_state_list(lines[1])
        alphabet = set(cls._parse_symbol_list(lines[2]))
        nfa = NFA(
            states={start_state, *accept_states},
            start_state=start_state,
            accept_states=accept_states,
            alphabet={symbol for symbol in alphabet if symbol != EPSILON},
        )

        for line in lines[3:]:
            source_str, symbol_str, target_str = line.split()
            source = int(source_str)
            target = int(target_str)
            symbol = cls._decode_symbol(symbol_str)
            nfa.add_transition(source, symbol, target)
        return nfa

    @classmethod
    def parse_dfa(cls, text: str) -> DFA:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 4:
            raise ValueError("DFA file is incomplete")

        start_state = cls._parse_single_state(lines[0])
        accept_states = cls._parse_state_list(lines[1])
        alphabet = set(cls._parse_symbol_list(lines[3]))
        dfa = DFA(
            states={start_state, *accept_states},
            start_state=start_state,
            accept_states=accept_states,
            alphabet=alphabet,
        )

        for line in lines[4:]:
            source_str, symbol_str, target_str = line.split()
            source = int(source_str)
            target = int(target_str)
            symbol = cls._decode_symbol(symbol_str)
            dfa.add_transition(source, symbol, target)
        return dfa

    @classmethod
    def format_nfa(cls, nfa: NFA) -> str:
        lines = [
            f"开始符:{nfa.start_state}",
            f"终结符:{cls._format_state_list(nfa.accept_states)}",
            f"符号集:{cls._format_symbol_list(nfa.alphabet)}",
        ]
        for source in sorted(nfa.transitions):
            for symbol in sorted(nfa.transitions[source], key=cls._sort_symbol):
                for target in sorted(nfa.transitions[source][symbol]):
                    lines.append(f"{source}\t{cls._encode_symbol(symbol)}\t{target}")
        return "\n".join(lines) + "\n"

    @classmethod
    def format_dfa(cls, dfa: DFA) -> str:
        lines = [
            f"开始符:{dfa.start_state};",
            f"终结符:{cls._format_state_list(dfa.accept_states)}",
            f"最大状态数:{max(dfa.states) if dfa.states else 0}",
            f"符号集:{cls._format_symbol_list(dfa.alphabet)}",
        ]
        for source in sorted(dfa.transitions):
            for symbol, target in sorted(
                dfa.transitions[source].items(),
                key=lambda item: cls._sort_symbol(item[0]),
            ):
                lines.append(f"{source}\t{cls._encode_symbol(symbol)}\t{target}")
        return "\n".join(lines) + "\n"

    @classmethod
    def _parse_single_state(cls, line: str) -> int:
        _, value = line.split(":", 1)
        value = value.replace(";", "").strip()
        return int(value)

    @classmethod
    def _parse_state_list(cls, line: str) -> set[int]:
        _, value = line.split(":", 1)
        items = [item.strip() for item in value.split(";") if item.strip()]
        return {int(item) for item in items}

    @classmethod
    def _parse_symbol_list(cls, line: str) -> list[str]:
        _, value = line.split(":", 1)
        items = [item.strip() for item in value.split(";") if item.strip()]
        return [cls._decode_symbol(item) for item in items]

    @classmethod
    def _format_state_list(cls, states: set[int]) -> str:
        return "".join(f"{state};" for state in sorted(states))

    @classmethod
    def _format_symbol_list(cls, symbols: set[str]) -> str:
        return "".join(f"{cls._encode_symbol(symbol)};" for symbol in sorted(symbols, key=cls._sort_symbol))

    @classmethod
    def _encode_symbol(cls, symbol: str) -> str:
        mapping = {"\n": r"\n", "\t": r"\t", "\r": r"\r", " ": r"\s"}
        return mapping.get(symbol, symbol)

    @classmethod
    def _decode_symbol(cls, symbol: str) -> str:
        mapping = {r"\n": "\n", r"\t": "\t", r"\r": "\r", r"\s": " "}
        return mapping.get(symbol, symbol)

    @classmethod
    def _sort_symbol(cls, symbol: str) -> tuple[int, str]:
        if symbol == EPSILON:
            return (0, symbol)
        return (1, cls._encode_symbol(symbol))
