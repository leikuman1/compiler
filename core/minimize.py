from __future__ import annotations

from .models import DFA, accept_partition_key


class DFAMinimizer:
    """Minimizes a DFA using iterative partition refinement."""

    @classmethod
    def minimize(cls, dfa: DFA) -> DFA:
        if not dfa.states:
            return dfa

        alphabet = sorted(dfa.alphabet)
        partitions = cls._initial_partitions(dfa)

        changed = True
        while changed:
            changed = False
            new_partitions: list[set[int]] = []
            index_by_state = cls._index_by_state(partitions)

            for partition in partitions:
                buckets: dict[tuple[int | None, ...], set[int]] = {}
                for state in partition:
                    signature = tuple(
                        index_by_state.get(dfa.transitions.get(state, {}).get(symbol))
                        for symbol in alphabet
                    )
                    buckets.setdefault(signature, set()).add(state)
                new_partitions.extend(buckets.values())
                if len(buckets) > 1:
                    changed = True
            partitions = new_partitions

        partitions = cls._order_partitions(partitions, dfa.start_state)
        part_to_new_state = {index: index for index, _ in enumerate(partitions)}
        old_to_part = cls._index_by_state(partitions)

        states = set(part_to_new_state.values())
        start_state = old_to_part[dfa.start_state]
        accept_states: set[int] = set()
        transitions: dict[int, dict[str, int]] = {}
        accept_metadata: dict[int, object] = {}
        state_subsets: dict[int, frozenset[int]] = {}

        for part_index, partition in enumerate(partitions):
            representative = min(partition)
            state_subsets[part_index] = frozenset(partition)
            if partition & dfa.accept_states:
                accept_states.add(part_index)
                metadata = dfa.accept_metadata.get(representative)
                if metadata is not None:
                    accept_metadata[part_index] = metadata
            for symbol, target in sorted(dfa.transitions.get(representative, {}).items()):
                transitions.setdefault(part_index, {})[symbol] = old_to_part[target]

        return DFA(
            states=states,
            start_state=start_state,
            accept_states=accept_states,
            alphabet=set(dfa.alphabet),
            transitions=transitions,
            accept_metadata=accept_metadata,
            state_subsets=state_subsets,
        )

    @classmethod
    def _initial_partitions(cls, dfa: DFA) -> list[set[int]]:
        accepting: dict[tuple[object, ...], set[int]] = {}
        non_accepting: set[int] = set()

        for state in dfa.states:
            if state in dfa.accept_states:
                key = accept_partition_key(dfa.accept_metadata.get(state))
                accepting.setdefault(key, set()).add(state)
            else:
                non_accepting.add(state)

        partitions = list(accepting.values())
        if non_accepting:
            partitions.append(non_accepting)
        return partitions

    @classmethod
    def _index_by_state(cls, partitions: list[set[int]]) -> dict[int, int]:
        mapping: dict[int, int] = {}
        for index, partition in enumerate(partitions):
            for state in partition:
                mapping[state] = index
        return mapping

    @classmethod
    def _order_partitions(cls, partitions: list[set[int]], start_state: int) -> list[set[int]]:
        start_partition = None
        others: list[set[int]] = []
        for partition in partitions:
            if start_state in partition:
                start_partition = partition
            else:
                others.append(partition)
        ordered = []
        if start_partition is not None:
            ordered.append(start_partition)
        ordered.extend(sorted(others, key=lambda group: min(group)))
        return ordered
