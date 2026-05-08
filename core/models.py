from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

StateId = int
Symbol = str
EPSILON = "#"


@dataclass(frozen=True, order=True)
class AcceptAction:
    """Metadata kept on accepting states for lexer disambiguation."""

    priority: int
    order: int
    token_name: str | None = None
    skip: bool = False


@dataclass
class NFA:
    states: set[StateId]
    start_state: StateId
    accept_states: set[StateId]
    alphabet: set[Symbol]
    transitions: dict[StateId, dict[Symbol, set[StateId]]] = field(default_factory=dict)
    accept_metadata: dict[StateId, Any] = field(default_factory=dict)

    def add_transition(self, source: StateId, symbol: Symbol, target: StateId) -> None:
        self.states.update({source, target})
        if symbol != EPSILON:
            self.alphabet.add(symbol)
        self.transitions.setdefault(source, {}).setdefault(symbol, set()).add(target)

    def next_states(self, source: StateId, symbol: Symbol) -> set[StateId]:
        return set(self.transitions.get(source, {}).get(symbol, set()))


@dataclass
class DFA:
    states: set[StateId]
    start_state: StateId
    accept_states: set[StateId]
    alphabet: set[Symbol]
    transitions: dict[StateId, dict[Symbol, StateId]] = field(default_factory=dict)
    accept_metadata: dict[StateId, Any] = field(default_factory=dict)
    state_subsets: dict[StateId, frozenset[StateId]] = field(default_factory=dict)

    def add_transition(self, source: StateId, symbol: Symbol, target: StateId) -> None:
        self.states.update({source, target})
        self.alphabet.add(symbol)
        self.transitions.setdefault(source, {})[symbol] = target

    def next_state(self, source: StateId, symbol: Symbol) -> StateId | None:
        return self.transitions.get(source, {}).get(symbol)


def accept_partition_key(metadata: Any) -> tuple[Any, ...]:
    """Creates a stable minimization key for accepting states."""

    if isinstance(metadata, AcceptAction):
        return ("accept-action", metadata.priority, metadata.order, metadata.token_name, metadata.skip)
    if metadata is None:
        return ("accept",)
    return ("accept-generic", repr(metadata))


def accept_choice_key(metadata: Any, state: StateId) -> tuple[Any, ...]:
    """Ranks accepting metadata when several NFA accept states merge into one DFA state."""

    if isinstance(metadata, AcceptAction):
        return (metadata.priority, metadata.order, state)
    return (0, 0, state)
