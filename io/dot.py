from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from compiler_project.core.models import DFA, NFA


class DotExporter:
    """Exports automata to DOT and optionally renders PNG with Graphviz."""

    @classmethod
    def is_dot_available(cls) -> bool:
        return shutil.which("dot") is not None

    @classmethod
    def export(cls, automaton: NFA | DFA, path: str | Path) -> None:
        Path(path).write_text(cls.to_dot(automaton), encoding="utf-8")

    @classmethod
    def to_dot(cls, automaton: NFA | DFA) -> str:
        lines = [
            "digraph Automaton {",
            "  rankdir=LR;",
            '  node [shape=circle, fontname="Microsoft YaHei"];',
            "  __start__ [shape=point];",
            f"  __start__ -> {automaton.start_state};",
        ]

        for state in sorted(automaton.states):
            shape = "doublecircle" if state in automaton.accept_states else "circle"
            lines.append(f"  {state} [shape={shape}];")

        edge_labels: dict[tuple[int, int], set[str]] = {}
        if isinstance(automaton, NFA):
            for source, mapping in automaton.transitions.items():
                for symbol, targets in mapping.items():
                    for target in targets:
                        edge_labels.setdefault((source, target), set()).add(cls._label(symbol))
        else:
            for source, mapping in automaton.transitions.items():
                for symbol, target in mapping.items():
                    edge_labels.setdefault((source, target), set()).add(cls._label(symbol))

        for (source, target), labels in sorted(edge_labels.items()):
            joined = ", ".join(sorted(labels))
            lines.append(f'  {source} -> {target} [label="{joined}"];')
        lines.append("}")
        return "\n".join(lines) + "\n"

    @classmethod
    def render_png(cls, dot_path: str | Path, png_path: str | Path) -> None:
        if not cls.is_dot_available():
            raise RuntimeError("Graphviz dot command is not available")
        subprocess.run(
            ["dot", "-Tpng", str(dot_path), "-o", str(png_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def _label(cls, symbol: str) -> str:
        mapping = {"\n": r"\n", "\t": r"\t", "\r": r"\r", " ": r"\s"}
        return mapping.get(symbol, symbol).replace('"', r"\"")
