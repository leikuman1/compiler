from __future__ import annotations

from dataclasses import dataclass

ENDMARK = "#"
EPSILON = "#"


class LRError(ValueError):
    """Raised when an LR(0) grammar or sentence cannot be analyzed."""


@dataclass(frozen=True)
class LRProduction:
    index: int
    lhs: str
    rhs: tuple[str, ...]

    @property
    def text(self) -> str:
        rhs_text = "".join(self.rhs) if self.rhs else EPSILON
        return f"{self.lhs}->{rhs_text}"


@dataclass(frozen=True)
class LRGrammar:
    start_symbol: str
    augmented_start: str
    nonterminals: tuple[str, ...]
    terminals: tuple[str, ...]
    productions: dict[str, tuple[LRProduction, ...]]
    production_order: tuple[LRProduction, ...]
    augmented_production: LRProduction

    def is_nonterminal(self, symbol: str) -> bool:
        return symbol in self.productions

    @property
    def all_productions(self) -> tuple[LRProduction, ...]:
        return (self.augmented_production,) + self.production_order


@dataclass(frozen=True)
class LRItem:
    production: LRProduction
    dot: int

    @property
    def next_symbol(self) -> str | None:
        if self.dot >= len(self.production.rhs):
            return None
        return self.production.rhs[self.dot]

    @property
    def is_complete(self) -> bool:
        return self.next_symbol is None

    def advance(self) -> LRItem:
        if self.is_complete:
            raise LRError("完整项目不能继续移动圆点。")
        return LRItem(self.production, self.dot + 1)

    @property
    def text(self) -> str:
        rhs = list(self.production.rhs)
        rhs.insert(self.dot, ".")
        return f"{self.production.lhs}->{''.join(rhs) if rhs else '.'}"


@dataclass(frozen=True)
class LRItemSet:
    index: int
    items: tuple[LRItem, ...]


@dataclass(frozen=True)
class LRTable:
    row_symbols: tuple[int, ...]
    action_symbols: tuple[str, ...]
    goto_symbols: tuple[str, ...]
    column_symbols: tuple[str, ...]
    entries: dict[tuple[int, str], str]

    def lookup(self, state: int, symbol: str) -> str | None:
        return self.entries.get((state, symbol))


@dataclass(frozen=True)
class LRAnalysisStep:
    index: int
    state_stack: str
    symbol_stack: str
    input_text: str
    action_text: str


@dataclass(frozen=True)
class LRAnalysisResult:
    accepted: bool
    message: str
    steps: tuple[LRAnalysisStep, ...]

    def step_at(self, index: int) -> LRAnalysisStep:
        return self.steps[index]

    def steps_prefix(self, count: int) -> tuple[LRAnalysisStep, ...]:
        return self.steps[:count]


def parse_lr_grammar(text: str) -> LRGrammar:
    lines = _collect_grammar_lines(text)
    productions_by_lhs: dict[str, list[LRProduction]] = {}
    production_order: list[LRProduction] = []
    nonterminals: list[str] = []
    next_index = 1

    for line in lines:
        lhs, alternatives = _split_production_line(line)
        if lhs not in productions_by_lhs:
            productions_by_lhs[lhs] = []
            nonterminals.append(lhs)
        for alternative in alternatives:
            rhs = _parse_alternative(alternative)
            production = LRProduction(index=next_index, lhs=lhs, rhs=rhs)
            productions_by_lhs[lhs].append(production)
            production_order.append(production)
            next_index += 1

    nonterminal_set = set(nonterminals)
    terminals: list[str] = []
    undefined_nonterminals: set[str] = set()

    for production in production_order:
        for symbol in production.rhs:
            if symbol in nonterminal_set:
                continue
            if _looks_like_nonterminal(symbol):
                undefined_nonterminals.add(symbol)
                continue
            if symbol not in terminals:
                terminals.append(symbol)

    if undefined_nonterminals:
        joined = "、".join(sorted(undefined_nonterminals))
        raise LRError(f"文法中存在未定义的非终结符：{joined}")

    start_symbol = nonterminals[0]
    augmented_start = _make_augmented_start(start_symbol, nonterminal_set)
    augmented_production = LRProduction(index=0, lhs=augmented_start, rhs=(start_symbol,))
    productions_by_lhs[augmented_start] = [augmented_production]

    return LRGrammar(
        start_symbol=start_symbol,
        augmented_start=augmented_start,
        nonterminals=tuple(nonterminals),
        terminals=tuple(terminals),
        productions={lhs: tuple(items) for lhs, items in productions_by_lhs.items()},
        production_order=tuple(production_order),
        augmented_production=augmented_production,
    )


def validate_lr0(grammar: LRGrammar) -> None:
    item_sets = build_lr_item_sets(grammar)
    build_lr_table(grammar, item_sets)


def build_lr_item_sets(grammar: LRGrammar) -> tuple[LRItemSet, ...]:
    start_item = LRItem(grammar.augmented_production, 0)
    start_kernel = frozenset(_closure(grammar, {start_item}))
    kernels: list[frozenset[LRItem]] = [start_kernel]
    seen: dict[frozenset[LRItem], int] = {start_kernel: 0}
    index = 0

    while index < len(kernels):
        current = kernels[index]
        for symbol in _transition_symbol_order(grammar):
            target = frozenset(_goto(grammar, current, symbol))
            if not target or target in seen:
                continue
            seen[target] = len(kernels)
            kernels.append(target)
        index += 1

    return tuple(
        LRItemSet(index=item_index, items=tuple(_sort_items(items)))
        for item_index, items in enumerate(kernels)
    )


def build_lr_table(grammar: LRGrammar, item_sets: tuple[LRItemSet, ...]) -> LRTable:
    state_map = {frozenset(item_set.items): item_set.index for item_set in item_sets}
    entries: dict[tuple[int, str], str] = {}

    for item_set in item_sets:
        item_frozen = frozenset(item_set.items)
        for symbol in _transition_symbol_order(grammar):
            target = frozenset(_goto(grammar, item_frozen, symbol))
            if not target:
                continue
            target_index = state_map[target]
            if symbol in grammar.terminals:
                _assign_table_entry(entries, item_set.index, symbol, f"s{target_index}")
            elif symbol in grammar.nonterminals:
                _assign_table_entry(entries, item_set.index, symbol, str(target_index))

        for item in item_set.items:
            if not item.is_complete:
                continue
            if item.production.index == 0:
                _assign_table_entry(entries, item_set.index, ENDMARK, "acc")
                continue
            for symbol in grammar.terminals + (ENDMARK,):
                _assign_table_entry(entries, item_set.index, symbol, f"r{item.production.index}")

    action_symbols = grammar.terminals + (ENDMARK,)
    goto_symbols = grammar.nonterminals
    return LRTable(
        row_symbols=tuple(item_set.index for item_set in item_sets),
        action_symbols=action_symbols,
        goto_symbols=goto_symbols,
        column_symbols=action_symbols + goto_symbols,
        entries=entries,
    )


def analyze_lr_sentence(grammar: LRGrammar, table: LRTable, sentence: str) -> LRAnalysisResult:
    normalized_sentence = "".join(sentence.split())
    if not normalized_sentence:
        normalized_sentence = ENDMARK
    elif not normalized_sentence.endswith(ENDMARK):
        normalized_sentence += ENDMARK

    input_symbols = list(normalized_sentence)
    state_stack = [0]
    symbol_stack = [ENDMARK]
    input_index = 0
    steps: list[LRAnalysisStep] = [
        _make_step(0, state_stack, symbol_stack, input_symbols[input_index:], "Initial State")
    ]
    step_index = 1
    production_by_index = {production.index: production for production in grammar.production_order}

    while True:
        current_state = state_stack[-1]
        current_symbol = input_symbols[input_index] if input_index < len(input_symbols) else None
        if current_symbol is None:
            message = "分析失败：输入串提前结束。"
            steps.append(_make_step(step_index, state_stack, symbol_stack, (), message))
            return LRAnalysisResult(False, message, tuple(steps))

        action = table.lookup(current_state, current_symbol)
        if action is None:
            message = f"分析失败：LR分析表 M[{current_state}, {current_symbol}] 为空。"
            steps.append(_make_step(step_index, state_stack, symbol_stack, input_symbols[input_index:], message))
            return LRAnalysisResult(False, message, tuple(steps))

        if action == "acc":
            message = "分析成功!是该文法的一个句子!"
            steps.append(_make_step(step_index, state_stack, symbol_stack, input_symbols[input_index:], message))
            return LRAnalysisResult(True, message, tuple(steps))

        if action.startswith("s"):
            next_state = _parse_state_action(action)
            symbol_stack.append(current_symbol)
            state_stack.append(next_state)
            input_index += 1
            steps.append(_make_step(step_index, state_stack, symbol_stack, input_symbols[input_index:], "移进"))
            step_index += 1
            continue

        if action.startswith("r"):
            production = production_by_index.get(_parse_reduce_action(action))
            if production is None:
                message = f"分析失败：归约动作 {action} 无对应产生式。"
                steps.append(_make_step(step_index, state_stack, symbol_stack, input_symbols[input_index:], message))
                return LRAnalysisResult(False, message, tuple(steps))

            for _ in production.rhs:
                if len(state_stack) <= 1 or len(symbol_stack) <= 1:
                    message = f"分析失败：归约 {production.text} 时栈内容不足。"
                    steps.append(_make_step(step_index, state_stack, symbol_stack, input_symbols[input_index:], message))
                    return LRAnalysisResult(False, message, tuple(steps))
                state_stack.pop()
                symbol_stack.pop()

            goto_state_text = table.lookup(state_stack[-1], production.lhs)
            if goto_state_text is None or not goto_state_text.isdigit():
                message = f"分析失败：GOTO({state_stack[-1]}, {production.lhs}) 为空。"
                steps.append(_make_step(step_index, state_stack, symbol_stack, input_symbols[input_index:], message))
                return LRAnalysisResult(False, message, tuple(steps))

            symbol_stack.append(production.lhs)
            state_stack.append(int(goto_state_text))
            steps.append(
                _make_step(
                    step_index,
                    state_stack,
                    symbol_stack,
                    input_symbols[input_index:],
                    f"归约用{production.text}",
                )
            )
            step_index += 1
            continue

        message = f"分析失败：未知动作 {action}。"
        steps.append(_make_step(step_index, state_stack, symbol_stack, input_symbols[input_index:], message))
        return LRAnalysisResult(False, message, tuple(steps))


def _collect_grammar_lines(text: str) -> list[str]:
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
        raise LRError("文法内容为空。")
    return lines


def _split_production_line(line: str) -> tuple[str, list[str]]:
    arrow = "->" if "->" in line else "→" if "→" in line else None
    if arrow is None:
        raise LRError(f"产生式缺少箭头：{line}")

    lhs, rhs = line.split(arrow, 1)
    if not lhs:
        raise LRError(f"产生式左部为空：{line}")
    if len(lhs) != 1 or not _looks_like_nonterminal(lhs):
        raise LRError(f"当前仅支持单个大写字母作为非终结符，非法左部：{lhs}")
    if not rhs:
        raise LRError(f"产生式右部为空：{line}")

    alternatives = rhs.split("|")
    if any(not alternative for alternative in alternatives):
        raise LRError(f"产生式存在空候选式：{line}")
    return lhs, alternatives


def _parse_alternative(alternative: str) -> tuple[str, ...]:
    if alternative == EPSILON:
        return ()
    if EPSILON in alternative:
        raise LRError(f"空产生式 {EPSILON} 必须单独作为一个候选式：{alternative}")
    return tuple(alternative)


def _make_augmented_start(start_symbol: str, nonterminals: set[str]) -> str:
    candidate = f"{start_symbol}'"
    if candidate not in nonterminals:
        return candidate
    suffix = 1
    while f"{start_symbol}'{suffix}" in nonterminals:
        suffix += 1
    return f"{start_symbol}'{suffix}"


def _closure(grammar: LRGrammar, items: set[LRItem]) -> set[LRItem]:
    closure_set = set(items)
    changed = True
    while changed:
        changed = False
        additions: set[LRItem] = set()
        for item in closure_set:
            symbol = item.next_symbol
            if symbol is None or not grammar.is_nonterminal(symbol):
                continue
            for production in grammar.productions[symbol]:
                new_item = LRItem(production, 0)
                if new_item not in closure_set:
                    additions.add(new_item)
        if additions:
            closure_set.update(additions)
            changed = True
    return closure_set


def _goto(grammar: LRGrammar, items: frozenset[LRItem] | set[LRItem], symbol: str) -> set[LRItem]:
    advanced = {item.advance() for item in items if item.next_symbol == symbol}
    if not advanced:
        return set()
    return _closure(grammar, advanced)


def _transition_symbol_order(grammar: LRGrammar) -> tuple[str, ...]:
    return grammar.nonterminals + grammar.terminals


def _sort_items(items: frozenset[LRItem] | set[LRItem]) -> list[LRItem]:
    return sorted(items, key=lambda item: (item.production.index, item.dot, item.production.lhs, item.production.rhs))


def _assign_table_entry(entries: dict[tuple[int, str], str], state: int, symbol: str, action: str) -> None:
    key = (state, symbol)
    existing = entries.get(key)
    if existing is None or existing == action:
        entries[key] = action
        return
    raise LRError(
        f"该文法不是LR(0)文法：分析表 M[{state}, {symbol}] 冲突，"
        f"{existing} 与 {action} 同时可用。"
    )


def _make_step(
    index: int,
    state_stack: list[int],
    symbol_stack: list[str],
    remaining_input: tuple[str, ...] | list[str],
    action_text: str,
) -> LRAnalysisStep:
    return LRAnalysisStep(
        index=index,
        state_stack=" ".join(str(state) for state in state_stack),
        symbol_stack="".join(symbol_stack),
        input_text="".join(remaining_input),
        action_text=action_text,
    )


def _parse_state_action(action: str) -> int:
    try:
        return int(action[1:])
    except ValueError as exc:
        raise LRError(f"非法移进动作：{action}") from exc


def _parse_reduce_action(action: str) -> int:
    try:
        return int(action[1:])
    except ValueError as exc:
        raise LRError(f"非法归约动作：{action}") from exc


def _looks_like_nonterminal(symbol: str) -> bool:
    return symbol.isascii() and symbol.isalpha() and symbol.isupper()
