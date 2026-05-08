from __future__ import annotations

from dataclasses import dataclass

from compiler_project.core.determinize import Determinizer
from compiler_project.core.minimize import DFAMinimizer
from compiler_project.core.models import AcceptAction, DFA, EPSILON, NFA
from compiler_project.core.regex import RegexParser
from compiler_project.core.thompson import ThompsonBuilder

from .specs import LexError, Token, TokenSpec


@dataclass
class CompiledLexer:
    dfa: DFA
    raw_dfa: DFA
    combined_nfa: NFA

    def scan(self, source: str) -> tuple[list[Token], list[LexError]]:
        tokens: list[Token] = []
        errors: list[LexError] = []
        index = 0
        line = 1
        column = 1

        while index < len(source):
            special = self._special_case(source, index)
            if special is not None:
                lexeme, message = special
                errors.append(LexError(message=message, lexeme=lexeme, line=line, column=column))
                line, column = self._advance_position(lexeme, line, column)
                index += len(lexeme)
                continue

            state = self.dfa.start_state
            last_accept: tuple[int, AcceptAction | None] | None = None
            probe = index

            while probe < len(source):
                char = source[probe]
                next_state = self.dfa.transitions.get(state, {}).get(char)
                if next_state is None:
                    break
                probe += 1
                state = next_state
                if state in self.dfa.accept_states:
                    action = self.dfa.accept_metadata.get(state)
                    last_accept = (probe, action)

            if last_accept is None:
                lexeme = source[index]
                errors.append(LexError("无法识别的字符", lexeme, line, column))
                line, column = self._advance_position(lexeme, line, column)
                index += 1
                continue

            end_index, action = last_accept
            lexeme = source[index:end_index]
            if action is None:
                token_name = "ACCEPT"
                skip = False
            else:
                token_name = action.token_name or "TOKEN"
                skip = action.skip

            if not skip:
                tokens.append(Token(token_name, lexeme, line, column))
            line, column = self._advance_position(lexeme, line, column)
            index = end_index

        return tokens, errors

    @staticmethod
    def _advance_position(text: str, line: int, column: int) -> tuple[int, int]:
        current_line = line
        current_column = column
        for char in text:
            if char == "\n":
                current_line += 1
                current_column = 1
            else:
                current_column += 1
        return current_line, current_column

    @staticmethod
    def _special_case(source: str, index: int) -> tuple[str, str] | None:
        if source.startswith("/*", index) and "*/" not in source[index + 2:]:
            return source[index:], "块注释未闭合"

        current = source[index]
        if current.isdigit():
            probe = index
            while probe < len(source) and source[probe].isdigit():
                probe += 1

            if probe < len(source) and source[probe] == ".":
                tail = probe + 1
                dot_count = 1
                while tail < len(source) and (source[tail].isdigit() or source[tail] == "."):
                    if source[tail] == ".":
                        dot_count += 1
                    tail += 1
                if dot_count > 1:
                    return source[index:tail], "数字常量不能包含多个小数点"

            if probe < len(source) and (source[probe].isalpha() or source[probe] == "_"):
                tail = probe + 1
                while tail < len(source) and (source[tail].isalnum() or source[tail] == "_"):
                    tail += 1
                return source[index:tail], "标识符不能以数字开头"

        return None


class LexerCompiler:
    """Compiles token specs into a minimized DFA-based lexer."""

    @classmethod
    def compile(cls, specs: list[TokenSpec]) -> CompiledLexer:
        parser = RegexParser()
        builder = ThompsonBuilder()
        nfas: list[tuple[NFA, AcceptAction]] = []

        for order, spec in enumerate(specs):
            regex_ir = parser.parse(spec.pattern)
            nfa = builder.build(regex_ir)
            accept_state = next(iter(nfa.accept_states))
            action = AcceptAction(
                priority=spec.priority,
                order=order,
                token_name=spec.name,
                skip=spec.skip,
            )
            nfa.accept_metadata[accept_state] = action
            nfas.append((nfa, action))

        combined_nfa = cls._combine_nfas(nfas)
        raw_dfa = Determinizer.convert(combined_nfa)
        minimized_dfa = DFAMinimizer.minimize(raw_dfa)
        return CompiledLexer(dfa=minimized_dfa, raw_dfa=raw_dfa, combined_nfa=combined_nfa)

    @classmethod
    def _combine_nfas(cls, entries: list[tuple[NFA, AcceptAction]]) -> NFA:
        next_state = 1
        start_state = 0
        states = {start_state}
        alphabet: set[str] = set()
        transitions: dict[int, dict[str, set[int]]] = {}
        accept_states: set[int] = set()
        accept_metadata: dict[int, AcceptAction] = {}

        for nfa, action in entries:
            mapping: dict[int, int] = {}
            for state in sorted(nfa.states):
                mapping[state] = next_state
                next_state += 1

            states.update(mapping.values())
            alphabet.update(nfa.alphabet)

            remapped_start = mapping[nfa.start_state]
            transitions.setdefault(start_state, {}).setdefault(EPSILON, set()).add(remapped_start)

            for source, symbol_map in nfa.transitions.items():
                for symbol, targets in symbol_map.items():
                    for target in targets:
                        remapped_source = mapping[source]
                        remapped_target = mapping[target]
                        transitions.setdefault(remapped_source, {}).setdefault(symbol, set()).add(remapped_target)

            for accept_state in nfa.accept_states:
                remapped_accept = mapping[accept_state]
                accept_states.add(remapped_accept)
                accept_metadata[remapped_accept] = action

        return NFA(
            states=states,
            start_state=start_state,
            accept_states=accept_states,
            alphabet=alphabet,
            transitions=transitions,
            accept_metadata=accept_metadata,
        )
