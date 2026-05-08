from __future__ import annotations

from dataclasses import dataclass

from .models import EPSILON, NFA
from .regex import CONCAT, RegexAtom, RegexIR


@dataclass
class _Fragment:
    start: int
    accept: int


class ThompsonBuilder:
    """Builds an epsilon-NFA from postfix regex IR."""

    def __init__(self) -> None:
        self._next_state = 0
        self._transitions: dict[int, dict[str, set[int]]] = {}
        self._states: set[int] = set()
        self._alphabet: set[str] = set()

    def build(self, regex_ir: RegexIR) -> NFA:
        self._next_state = 0
        self._transitions = {}
        self._states = set()
        self._alphabet = set()

        fragments: list[_Fragment] = []
        for token in regex_ir:
            if isinstance(token, RegexAtom):
                fragments.append(self._build_atom(token))
            elif token == CONCAT:
                right = fragments.pop()
                left = fragments.pop()
                self._add_transition(left.accept, EPSILON, right.start)
                fragments.append(_Fragment(left.start, right.accept))
            elif token == "|":
                right = fragments.pop()
                left = fragments.pop()
                start = self._new_state()
                accept = self._new_state()
                self._add_transition(start, EPSILON, left.start)
                self._add_transition(start, EPSILON, right.start)
                self._add_transition(left.accept, EPSILON, accept)
                self._add_transition(right.accept, EPSILON, accept)
                fragments.append(_Fragment(start, accept))
            elif token == "*":
                fragment = fragments.pop()
                start = self._new_state()
                accept = self._new_state()
                self._add_transition(start, EPSILON, fragment.start)
                self._add_transition(start, EPSILON, accept)
                self._add_transition(fragment.accept, EPSILON, fragment.start)
                self._add_transition(fragment.accept, EPSILON, accept)
                fragments.append(_Fragment(start, accept))
            elif token == "+":
                fragment = fragments.pop()
                start = self._new_state()
                accept = self._new_state()
                self._add_transition(start, EPSILON, fragment.start)
                self._add_transition(fragment.accept, EPSILON, fragment.start)
                self._add_transition(fragment.accept, EPSILON, accept)
                fragments.append(_Fragment(start, accept))
            elif token == "?":
                fragment = fragments.pop()
                start = self._new_state()
                accept = self._new_state()
                self._add_transition(start, EPSILON, fragment.start)
                self._add_transition(start, EPSILON, accept)
                self._add_transition(fragment.accept, EPSILON, accept)
                fragments.append(_Fragment(start, accept))
            else:
                raise ValueError(f"unsupported regex token: {token}")

        if len(fragments) != 1:
            raise ValueError("invalid postfix regex")

        fragment = fragments[0]
        return NFA(
            states=set(self._states),
            start_state=fragment.start,
            accept_states={fragment.accept},
            alphabet=set(self._alphabet),
            transitions={
                state: {symbol: set(targets) for symbol, targets in mapping.items()}
                for state, mapping in self._transitions.items()
            },
        )

    def _build_atom(self, atom: RegexAtom) -> _Fragment:
        start = self._new_state()
        accept = self._new_state()
        for symbol in atom.symbols:
            self._add_transition(start, symbol, accept)
        return _Fragment(start, accept)

    def _new_state(self) -> int:
        state = self._next_state
        self._next_state += 1
        self._states.add(state)
        return state

    def _add_transition(self, source: int, symbol: str, target: int) -> None:
        self._states.update({source, target})
        if symbol != EPSILON:
            self._alphabet.add(symbol)
        self._transitions.setdefault(source, {}).setdefault(symbol, set()).add(target)
