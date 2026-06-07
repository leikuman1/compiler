from __future__ import annotations

from dataclasses import dataclass

EPSILON = "$"
ENDMARK = "#"


class LL1Error(ValueError):
    """Raised when the grammar or sentence cannot be analyzed as LL(1)."""


@dataclass(frozen=True)
class Production:
    lhs: str
    rhs: tuple[str, ...]

    @property
    def text(self) -> str:
        return f"{self.lhs}->{''.join(self.rhs) if self.rhs else EPSILON}"


@dataclass(frozen=True)
class Grammar:
    start_symbol: str
    nonterminals: tuple[str, ...]
    terminals: tuple[str, ...]
    productions: dict[str, tuple[Production, ...]]
    production_order: tuple[Production, ...]

    def is_nonterminal(self, symbol: str) -> bool:
        return symbol in self.productions


@dataclass(frozen=True)
class PredictTable:
    row_symbols: tuple[str, ...]
    column_symbols: tuple[str, ...]
    entries: dict[tuple[str, str], Production]

    def lookup(self, nonterminal: str, terminal: str) -> Production | None:
        return self.entries.get((nonterminal, terminal))


@dataclass(frozen=True)
class AnalysisStep:
    index: int
    stack_text: str
    input_text: str
    production_text: str


@dataclass(frozen=True)
class AnalysisResult:
    accepted: bool
    message: str
    steps: tuple[AnalysisStep, ...]

    def step_at(self, index: int) -> AnalysisStep:
        return self.steps[index]

    def steps_prefix(self, count: int) -> tuple[AnalysisStep, ...]:
        return self.steps[:count]


def parse_grammar(text: str) -> Grammar:
    raw_lines = text.replace("\ufeff", "").splitlines()
    lines: list[str] = []
    started = False
    for raw_line in raw_lines:
        line = "".join(raw_line.split())
        if not line:
            if started:
                break
            continue
        started = True
        lines.append(line)

    if not lines:
        raise LL1Error("文法内容为空。")

    productions_by_lhs: dict[str, list[Production]] = {}
    production_order: list[Production] = []
    nonterminals: list[str] = []

    for line in lines:
        lhs, alternatives = _split_production_line(line)
        if lhs not in productions_by_lhs:
            productions_by_lhs[lhs] = []
            nonterminals.append(lhs)
        for alternative in alternatives:
            rhs = _parse_alternative(alternative)
            production = Production(lhs=lhs, rhs=rhs)
            productions_by_lhs[lhs].append(production)
            production_order.append(production)

    nonterminal_set = set(nonterminals)
    terminals: set[str] = set()
    undefined_nonterminals: set[str] = set()

    for production in production_order:
        for symbol in production.rhs:
            if symbol == EPSILON:
                continue
            if symbol in nonterminal_set:
                continue
            if _looks_like_nonterminal(symbol):
                undefined_nonterminals.add(symbol)
                continue
            terminals.add(symbol)

    if undefined_nonterminals:
        joined = "、".join(sorted(undefined_nonterminals))
        raise LL1Error(f"文法中存在未定义的非终结符：{joined}")

    return Grammar(
        start_symbol=nonterminals[0],
        nonterminals=tuple(nonterminals),
        terminals=tuple(sorted(terminals)),
        productions={lhs: tuple(items) for lhs, items in productions_by_lhs.items()},
        production_order=tuple(production_order),
    )


def validate_ll1(grammar: Grammar) -> None:
    first_sets = compute_first(grammar)
    follow_sets = compute_follow(grammar, first_sets)
    build_predict_table(grammar, first_sets, follow_sets)


def compute_first(grammar: Grammar) -> dict[str, set[str]]:
    first_sets = {symbol: set() for symbol in grammar.nonterminals}
    changed = True

    while changed:
        changed = False
        for production in grammar.production_order:
            target = first_sets[production.lhs]
            before = len(target)
            target.update(_first_of_sequence(production.rhs, grammar, first_sets))
            if len(target) != before:
                changed = True

    return first_sets


def compute_follow(grammar: Grammar, first_sets: dict[str, set[str]]) -> dict[str, set[str]]:
    follow_sets = {symbol: set() for symbol in grammar.nonterminals}
    follow_sets[grammar.start_symbol].add(ENDMARK)

    changed = True
    while changed:
        changed = False
        for production in grammar.production_order:
            lhs_follow = follow_sets[production.lhs]
            rhs = production.rhs
            for index, symbol in enumerate(rhs):
                if not grammar.is_nonterminal(symbol):
                    continue
                suffix = rhs[index + 1 :]
                suffix_first = _first_of_sequence(suffix, grammar, first_sets)

                before = len(follow_sets[symbol])
                follow_sets[symbol].update(suffix_first - {EPSILON})
                if EPSILON in suffix_first or not suffix:
                    follow_sets[symbol].update(lhs_follow)
                if len(follow_sets[symbol]) != before:
                    changed = True

    return follow_sets


def build_predict_table(
    grammar: Grammar,
    first_sets: dict[str, set[str]],
    follow_sets: dict[str, set[str]],
) -> PredictTable:
    entries: dict[tuple[str, str], Production] = {}
    for production in grammar.production_order:
        first_alpha = _first_of_sequence(production.rhs, grammar, first_sets)
        for terminal in sorted(first_alpha - {EPSILON}):
            _assign_table_entry(entries, production.lhs, terminal, production)

        if EPSILON in first_alpha:
            for terminal in _sort_symbols(follow_sets[production.lhs]):
                _assign_table_entry(entries, production.lhs, terminal, production)

    return PredictTable(
        row_symbols=grammar.nonterminals,
        column_symbols=tuple(_sort_symbols(set(grammar.terminals) | {ENDMARK})),
        entries=entries,
    )


def analyze_sentence(grammar: Grammar, table: PredictTable, sentence: str) -> AnalysisResult:
    normalized_sentence = "".join(sentence.split())
    if not normalized_sentence:
        normalized_sentence = ENDMARK
    elif not normalized_sentence.endswith(ENDMARK):
        normalized_sentence += ENDMARK

    input_symbols = list(normalized_sentence)
    stack = [ENDMARK, grammar.start_symbol]
    steps = [
        AnalysisStep(
            index=1,
            stack_text="".join(stack),
            input_text="".join(input_symbols),
            production_text="Initial State",
        )
    ]
    step_index = 2
    input_index = 0

    while stack:
        top = stack[-1]
        current = input_symbols[input_index] if input_index < len(input_symbols) else None

        if top == ENDMARK and current == ENDMARK:
            return AnalysisResult(
                accepted=True,
                message="分析成功，是该文法的一个句子。",
                steps=tuple(steps),
            )

        if current is None:
            steps.append(
                AnalysisStep(
                    index=step_index,
                    stack_text="".join(stack),
                    input_text="",
                    production_text="错误：输入串提前结束",
                )
            )
            return AnalysisResult(
                accepted=False,
                message="分析失败：输入串提前结束。",
                steps=tuple(steps),
            )

        if not grammar.is_nonterminal(top):
            if top == current:
                stack.pop()
                input_index += 1
                steps.append(
                    AnalysisStep(
                        index=step_index,
                        stack_text="".join(stack),
                        input_text="".join(input_symbols[input_index:]),
                        production_text="匹配!",
                    )
                )
                step_index += 1
                continue

            steps.append(
                AnalysisStep(
                    index=step_index,
                    stack_text="".join(stack),
                    input_text="".join(input_symbols[input_index:]),
                    production_text=f"错误：栈顶符号 {top} 与输入符号 {current} 不匹配",
                )
            )
            return AnalysisResult(
                accepted=False,
                message=f"分析失败：栈顶符号 {top} 与输入符号 {current} 不匹配。",
                steps=tuple(steps),
            )

        production = table.lookup(top, current)
        if production is None:
            steps.append(
                AnalysisStep(
                    index=step_index,
                    stack_text="".join(stack),
                    input_text="".join(input_symbols[input_index:]),
                    production_text=f"错误：预测分析表 M[{top}, {current}] 为空",
                )
            )
            return AnalysisResult(
                accepted=False,
                message=f"分析失败：预测分析表 M[{top}, {current}] 为空。",
                steps=tuple(steps),
            )

        stack.pop()
        if production.rhs != (EPSILON,):
            for symbol in reversed(production.rhs):
                stack.append(symbol)

        steps.append(
            AnalysisStep(
                index=step_index,
                stack_text="".join(stack),
                input_text="".join(input_symbols[input_index:]),
                production_text=production.text,
            )
        )
        step_index += 1

    return AnalysisResult(
        accepted=False,
        message="分析失败：符号栈已空，但输入尚未处理完成。",
        steps=tuple(steps),
    )


def _split_production_line(line: str) -> tuple[str, list[str]]:
    arrow = "->" if "->" in line else "→" if "→" in line else None
    if arrow is None:
        raise LL1Error(f"产生式缺少箭头：{line}")

    lhs, rhs = line.split(arrow, 1)
    if not lhs:
        raise LL1Error(f"产生式左部为空：{line}")
    if len(lhs) != 1:
        raise LL1Error(f"当前仅支持单字符非终结符，非法左部：{lhs}")
    if not rhs:
        raise LL1Error(f"产生式右部为空：{line}")

    alternatives = rhs.split("|")
    if any(not alternative for alternative in alternatives):
        raise LL1Error(f"产生式存在空候选式：{line}")
    return lhs, alternatives


def _parse_alternative(alternative: str) -> tuple[str, ...]:
    if alternative == EPSILON:
        return (EPSILON,)
    if EPSILON in alternative:
        raise LL1Error(f"空串 {EPSILON} 必须单独作为一个候选式：{alternative}")
    return tuple(alternative)


def _first_of_sequence(
    symbols: tuple[str, ...],
    grammar: Grammar,
    first_sets: dict[str, set[str]],
) -> set[str]:
    if not symbols:
        return {EPSILON}
    if symbols == (EPSILON,):
        return {EPSILON}

    result: set[str] = set()
    nullable_prefix = True

    for symbol in symbols:
        if symbol == EPSILON:
            result.add(EPSILON)
            break

        if grammar.is_nonterminal(symbol):
            result.update(first_sets[symbol] - {EPSILON})
            if EPSILON in first_sets[symbol]:
                continue
            nullable_prefix = False
            break

        result.add(symbol)
        nullable_prefix = False
        break

    if nullable_prefix:
        result.add(EPSILON)
    return result


def _assign_table_entry(
    entries: dict[tuple[str, str], Production],
    nonterminal: str,
    terminal: str,
    production: Production,
) -> None:
    key = (nonterminal, terminal)
    existing = entries.get(key)
    if existing is None:
        entries[key] = production
        return
    if existing.text == production.text:
        return
    raise LL1Error(
        f"该文法不是LL(1)文法：预测分析表 M[{nonterminal}, {terminal}] 冲突，"
        f"候选式 {existing.text} 与 {production.text} 同时可用。"
    )


def _looks_like_nonterminal(symbol: str) -> bool:
    return symbol.isascii() and symbol.isalpha() and symbol.isupper()


def _sort_symbols(symbols: set[str]) -> list[str]:
    return sorted(symbols, key=lambda symbol: (symbol == ENDMARK, symbol == EPSILON, symbol))

