from __future__ import annotations

from collections import deque

from .models import DFA, EPSILON, NFA, accept_choice_key


class Determinizer:
    """Converts epsilon-NFA to DFA using subset construction."""

    @classmethod
    def convert(cls, nfa: NFA) -> DFA:
        alphabet = sorted(symbol for symbol in nfa.alphabet if symbol != EPSILON)
        start_subset = frozenset(cls.epsilon_closure(nfa, {nfa.start_state}))
        subset_to_state = {start_subset: 0}
        state_to_subset = {0: start_subset}
        queue = deque([start_subset])
        transitions: dict[int, dict[str, int]] = {}
        accept_states: set[int] = set()
        accept_metadata: dict[int, object] = {}

        while queue:
            subset = queue.popleft()
            state_id = subset_to_state[subset]

            best_accept = cls._best_accept(nfa, subset)
            if best_accept is not None or subset & nfa.accept_states:
                accept_states.add(state_id)
                if best_accept is not None:
                    accept_metadata[state_id] = best_accept

            for symbol in alphabet:
                moved = cls.move(nfa, subset, symbol)
                if not moved:
                    continue
                target_subset = frozenset(cls.epsilon_closure(nfa, moved))
                if target_subset not in subset_to_state:
                    new_state = len(subset_to_state)
                    subset_to_state[target_subset] = new_state
                    state_to_subset[new_state] = target_subset
                    queue.append(target_subset)
                transitions.setdefault(state_id, {})[symbol] = subset_to_state[target_subset]

        return DFA(
            states=set(state_to_subset),
            start_state=0,
            accept_states=accept_states,
            alphabet=set(alphabet),
            transitions=transitions,
            accept_metadata=accept_metadata,
            state_subsets=state_to_subset,
        )

    @classmethod
    def epsilon_closure(cls, nfa: NFA, states: set[int]) -> set[int]:
        closure = set(states)
        stack = list(states)
        while stack:
            state = stack.pop()
            for target in nfa.transitions.get(state, {}).get(EPSILON, set()):
                if target not in closure:
                    closure.add(target)
                    stack.append(target)
        return closure

    @classmethod
    def move(cls, nfa: NFA, states: frozenset[int] | set[int], symbol: str) -> set[int]:
        targets: set[int] = set()
        for state in states:
            targets.update(nfa.transitions.get(state, {}).get(symbol, set()))
        return targets

    @classmethod
    def _best_accept(cls, nfa: NFA, subset: frozenset[int]) -> object | None:
        candidates = [
            (state, nfa.accept_metadata.get(state))
            for state in subset
            if state in nfa.accept_states and state in nfa.accept_metadata
        ]
        if not candidates:
            return None
        best_state, best_metadata = min(
            candidates,
            key=lambda item: accept_choice_key(item[1], item[0]),
        )
        _ = best_state
        return best_metadata
