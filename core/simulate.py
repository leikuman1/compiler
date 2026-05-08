from __future__ import annotations

from .determinize import Determinizer
from .models import DFA, NFA


class AutomataSimulator:
    """Runs input strings on NFA or DFA objects."""

    @classmethod
    def accepts_nfa(cls, nfa: NFA, text: str) -> bool:
        current = Determinizer.epsilon_closure(nfa, {nfa.start_state})
        for char in text:
            moved = Determinizer.move(nfa, current, char)
            current = Determinizer.epsilon_closure(nfa, moved)
            if not current:
                return False
        return bool(current & nfa.accept_states)

    @classmethod
    def accepts_dfa(cls, dfa: DFA, text: str) -> bool:
        state = dfa.start_state
        for char in text:
            next_state = dfa.transitions.get(state, {}).get(char)
            if next_state is None:
                return False
            state = next_state
        return state in dfa.accept_states
