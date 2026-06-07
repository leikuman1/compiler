from __future__ import annotations

from dataclasses import dataclass

ENDMARK = "#"
EPSILON = "$"
DEFAULT_EXPRESSION_GRAMMAR = "E->E+T|E-T|T\nT->T*F|T/F|F\nF->(E)|d"

Number = int | float


class SLRTranslationError(ValueError):
    """Raised when an SLR(1) grammar or expression cannot be translated."""


@dataclass(frozen=True)
class SLRProduction:
    index: int
    lhs: str
    rhs: tuple[str, ...]

    @property
    def text(self) -> str:
        rhs_text = "".join(self.rhs) if self.rhs else EPSILON
        return f"{self.lhs}->{rhs_text}"


@dataclass(frozen=True)
class SLRGrammar:
    start_symbol: str
    augmented_start: str
    nonterminals: tuple[str, ...]
    terminals: tuple[str, ...]
    productions: dict[str, tuple[SLRProduction, ...]]
    production_order: tuple[SLRProduction, ...]
    augmented_production: SLRProduction

    def is_nonterminal(self, symbol: str) -> bool:
        return symbol in self.productions

    @property
    def all_productions(self) -> tuple[SLRProduction, ...]:
        return (self.augmented_production,) + self.production_order


@dataclass(frozen=True)
class SLRItem:
    production: SLRProduction
    dot: int

    @property
    def next_symbol(self) -> str | None:
        if self.dot >= len(self.production.rhs):
            return None
        return self.production.rhs[self.dot]

    @property
    def is_complete(self) -> bool:
        return self.next_symbol is None

    def advance(self) -> SLRItem:
        if self.is_complete:
            raise SLRTranslationError("完整项目不能继续移动圆点。")
        return SLRItem(self.production, self.dot + 1)

    @property
    def text(self) -> str:
        rhs = list(self.production.rhs)
        rhs.insert(self.dot, ".")
        return f"{self.production.lhs}->{''.join(rhs) if rhs else '.'}"


@dataclass(frozen=True)
class SLRItemSet:
    index: int
    items: tuple[SLRItem, ...]


@dataclass(frozen=True)
class SLRTable:
    row_symbols: tuple[int, ...]
    action_symbols: tuple[str, ...]
    goto_symbols: tuple[str, ...]
    column_symbols: tuple[str, ...]
    entries: dict[tuple[int, str], str]

    def lookup(self, state: int, symbol: str) -> str | None:
        return self.entries.get((state, symbol))


@dataclass(frozen=True)
class TranslationStep:
    index: int
    state_stack: str
    symbol_stack: str
    input_text: str
    action_text: str
    goto_text: str
    semantic_stack: str


@dataclass(frozen=True)
class Quadruple:
    index: int
    operator: str
    arg1: str
    arg2: str
    result: str

    @property
    def text(self) -> str:
        return f"({self.operator} , {self.arg1}, {self.arg2}, {self.result})"


@dataclass(frozen=True)
class TranslationResult:
    accepted: bool
    message: str
    steps: tuple[TranslationStep, ...]
    quadruples: tuple[Quadruple, ...]
    value: Number | None
    result_place: str

    def step_at(self, index: int) -> TranslationStep:
        return self.steps[index]

    def steps_prefix(self, count: int) -> tuple[TranslationStep, ...]:
        return self.steps[:count]


@dataclass(frozen=True)
class _ExpressionToken:
    symbol: str
    lexeme: str
    value: Number | None = None


@dataclass(frozen=True)
class _SemanticValue:
    symbol: str
    place: str
    value: Number | None = None

    @property
    def display_text(self) -> str:
        if self.value is None:
            return self.place
        formatted = _format_number(self.value)
        if self.place == formatted:
            return self.place
        return f"{self.place}={formatted}"


def parse_expression_grammar(text: str) -> SLRGrammar:
    lines = _collect_grammar_lines(text)
    productions_by_lhs: dict[str, list[SLRProduction]] = {}
    production_order: list[SLRProduction] = []
    nonterminals: list[str] = []
    next_index = 1

    for line in lines:
        lhs, alternatives = _split_production_line(line)
        if lhs not in productions_by_lhs:
            productions_by_lhs[lhs] = []
            nonterminals.append(lhs)
        for alternative in alternatives:
            rhs = _parse_alternative(alternative)
            production = SLRProduction(index=next_index, lhs=lhs, rhs=rhs)
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
            if symbol not in terminals and symbol != EPSILON:
                terminals.append(symbol)

    if undefined_nonterminals:
        joined = "、".join(sorted(undefined_nonterminals))
        raise SLRTranslationError(f"文法中存在未定义的非终结符：{joined}")

    start_symbol = nonterminals[0]
    augmented_start = _make_augmented_start(start_symbol, nonterminal_set)
    augmented_production = SLRProduction(index=0, lhs=augmented_start, rhs=(start_symbol,))
    productions_by_lhs[augmented_start] = [augmented_production]

    return SLRGrammar(
        start_symbol=start_symbol,
        augmented_start=augmented_start,
        nonterminals=tuple(nonterminals),
        terminals=tuple(terminals),
        productions={lhs: tuple(items) for lhs, items in productions_by_lhs.items()},
        production_order=tuple(production_order),
        augmented_production=augmented_production,
    )


def build_slr_item_sets(grammar: SLRGrammar) -> tuple[SLRItemSet, ...]:
    start_item = SLRItem(grammar.augmented_production, 0)
    start_kernel = frozenset(_closure(grammar, {start_item}))
    kernels: list[frozenset[SLRItem]] = [start_kernel]
    seen: dict[frozenset[SLRItem], int] = {start_kernel: 0}
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
        SLRItemSet(index=item_index, items=tuple(_sort_items(items)))
        for item_index, items in enumerate(kernels)
    )


def build_slr_table(grammar: SLRGrammar, item_sets: tuple[SLRItemSet, ...]) -> SLRTable:
    state_map = {frozenset(item_set.items): item_set.index for item_set in item_sets}
    follow_sets = _compute_follow(grammar)
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
            for symbol in follow_sets[item.production.lhs]:
                _assign_table_entry(entries, item_set.index, symbol, f"r{item.production.index}")

    action_symbols = grammar.terminals + (ENDMARK,)
    goto_symbols = grammar.nonterminals
    return SLRTable(
        row_symbols=tuple(item_set.index for item_set in item_sets),
        action_symbols=action_symbols,
        goto_symbols=goto_symbols,
        column_symbols=action_symbols + goto_symbols,
        entries=entries,
    )


def translate_expression(grammar: SLRGrammar, table: SLRTable, expression: str) -> TranslationResult:
    tokens = _tokenize_expression(expression)
    state_stack = [0]
    symbol_stack = [ENDMARK]
    semantic_stack = [_SemanticValue(ENDMARK, ENDMARK)]
    input_index = 0
    steps: list[TranslationStep] = [
        _make_step(0, state_stack, symbol_stack, tokens[input_index:], "Initial State", "", semantic_stack)
    ]
    quadruples: list[Quadruple] = []
    production_by_index = {production.index: production for production in grammar.production_order}
    next_temp_index = 1
    step_index = 1

    while True:
        current_state = state_stack[-1]
        current_token = tokens[input_index] if input_index < len(tokens) else None
        if current_token is None:
            return _failed_result(
                "分析失败：输入串提前结束。",
                step_index,
                state_stack,
                symbol_stack,
                (),
                semantic_stack,
                steps,
                quadruples,
            )

        action = table.lookup(current_state, current_token.symbol)
        if action is None:
            return _failed_result(
                f"分析失败：SLR(1)分析表 M[{current_state}, {current_token.symbol}] 为空。",
                step_index,
                state_stack,
                symbol_stack,
                tokens[input_index:],
                semantic_stack,
                steps,
                quadruples,
            )

        if action == "acc":
            final_value = semantic_stack[-1].value if semantic_stack else None
            final_place = semantic_stack[-1].place if semantic_stack else ""
            value_text = _format_number(final_value) if final_value is not None else "未知"
            message = f"翻译成功，表达式值为 {value_text}。"
            steps.append(_make_step(step_index, state_stack, symbol_stack, tokens[input_index:], "acc", "", semantic_stack))
            return TranslationResult(True, message, tuple(steps), tuple(quadruples), final_value, final_place)

        if action.startswith("s"):
            next_state = _parse_state_action(action)
            state_stack.append(next_state)
            symbol_stack.append(current_token.symbol)
            semantic_stack.append(_semantic_for_shift(current_token))
            input_index += 1
            steps.append(_make_step(step_index, state_stack, symbol_stack, tokens[input_index:], action, "", semantic_stack))
            step_index += 1
            continue

        if action.startswith("r"):
            production = production_by_index.get(_parse_reduce_action(action))
            if production is None:
                return _failed_result(
                    f"分析失败：归约动作 {action} 无对应产生式。",
                    step_index,
                    state_stack,
                    symbol_stack,
                    tokens[input_index:],
                    semantic_stack,
                    steps,
                    quadruples,
                )

            rhs_len = len(production.rhs)
            if len(state_stack) <= rhs_len or len(symbol_stack) <= rhs_len or len(semantic_stack) <= rhs_len:
                return _failed_result(
                    f"分析失败：归约 {production.text} 时栈内容不足。",
                    step_index,
                    state_stack,
                    symbol_stack,
                    tokens[input_index:],
                    semantic_stack,
                    steps,
                    quadruples,
                )

            rhs_values = semantic_stack[-rhs_len:] if rhs_len else []
            try:
                semantic_value, next_temp_index = _apply_semantic_action(
                    production,
                    rhs_values,
                    quadruples,
                    next_temp_index,
                )
            except SLRTranslationError as exc:
                return _failed_result(
                    f"分析失败：{exc}",
                    step_index,
                    state_stack,
                    symbol_stack,
                    tokens[input_index:],
                    semantic_stack,
                    steps,
                    quadruples,
                )

            for _ in range(rhs_len):
                state_stack.pop()
                symbol_stack.pop()
                semantic_stack.pop()

            goto_state_text = table.lookup(state_stack[-1], production.lhs)
            if goto_state_text is None or not goto_state_text.isdigit():
                return _failed_result(
                    f"分析失败：GOTO({state_stack[-1]}, {production.lhs}) 为空。",
                    step_index,
                    state_stack,
                    symbol_stack,
                    tokens[input_index:],
                    semantic_stack,
                    steps,
                    quadruples,
                )

            symbol_stack.append(production.lhs)
            state_stack.append(int(goto_state_text))
            semantic_stack.append(semantic_value)
            steps.append(
                _make_step(
                    step_index,
                    state_stack,
                    symbol_stack,
                    tokens[input_index:],
                    f"{action} {production.text}",
                    goto_state_text,
                    semantic_stack,
                )
            )
            step_index += 1
            continue

        return _failed_result(
            f"分析失败：未知动作 {action}。",
            step_index,
            state_stack,
            symbol_stack,
            tokens[input_index:],
            semantic_stack,
            steps,
            quadruples,
        )


def _collect_grammar_lines(text: str) -> list[str]:
    raw_lines = text.replace("\ufeff", "").splitlines()
    lines: list[str] = []
    for raw_line in raw_lines:
        line = "".join(raw_line.split())
        if line:
            lines.append(line)

    if not lines:
        raise SLRTranslationError("文法内容为空。")
    return lines


def _split_production_line(line: str) -> tuple[str, list[str]]:
    arrow = "->" if "->" in line else "→" if "→" in line else None
    if arrow is None:
        raise SLRTranslationError(f"产生式缺少箭头：{line}")

    lhs, rhs = line.split(arrow, 1)
    if not lhs:
        raise SLRTranslationError(f"产生式左部为空：{line}")
    if len(lhs) != 1 or not _looks_like_nonterminal(lhs):
        raise SLRTranslationError(f"当前仅支持单个大写字母作为非终结符，非法左部：{lhs}")
    if not rhs:
        raise SLRTranslationError(f"产生式右部为空：{line}")

    alternatives = rhs.split("|")
    if any(not alternative for alternative in alternatives):
        raise SLRTranslationError(f"产生式存在空候选式：{line}")
    return lhs, alternatives


def _parse_alternative(alternative: str) -> tuple[str, ...]:
    if alternative == EPSILON:
        return ()
    if EPSILON in alternative:
        raise SLRTranslationError(f"空产生式 {EPSILON} 必须单独作为一个候选式：{alternative}")
    if ENDMARK in alternative:
        raise SLRTranslationError(f"{ENDMARK} 是输入结束符，不能出现在文法右部：{alternative}")
    return tuple(alternative)


def _make_augmented_start(start_symbol: str, nonterminals: set[str]) -> str:
    candidate = f"{start_symbol}'"
    if candidate not in nonterminals:
        return candidate
    suffix = 1
    while f"{start_symbol}'{suffix}" in nonterminals:
        suffix += 1
    return f"{start_symbol}'{suffix}"


def _closure(grammar: SLRGrammar, items: set[SLRItem]) -> set[SLRItem]:
    closure_set = set(items)
    changed = True
    while changed:
        changed = False
        additions: set[SLRItem] = set()
        for item in closure_set:
            symbol = item.next_symbol
            if symbol is None or not grammar.is_nonterminal(symbol):
                continue
            for production in grammar.productions[symbol]:
                new_item = SLRItem(production, 0)
                if new_item not in closure_set:
                    additions.add(new_item)
        if additions:
            closure_set.update(additions)
            changed = True
    return closure_set


def _goto(grammar: SLRGrammar, items: frozenset[SLRItem] | set[SLRItem], symbol: str) -> set[SLRItem]:
    advanced = {item.advance() for item in items if item.next_symbol == symbol}
    if not advanced:
        return set()
    return _closure(grammar, advanced)


def _transition_symbol_order(grammar: SLRGrammar) -> tuple[str, ...]:
    return grammar.nonterminals + grammar.terminals


def _sort_items(items: frozenset[SLRItem] | set[SLRItem]) -> list[SLRItem]:
    return sorted(items, key=lambda item: (item.production.index, item.dot, item.production.lhs, item.production.rhs))


def _compute_first(grammar: SLRGrammar) -> dict[str, set[str]]:
    first_sets: dict[str, set[str]] = {symbol: set() for symbol in grammar.nonterminals}
    for terminal in grammar.terminals:
        first_sets[terminal] = {terminal}

    changed = True
    while changed:
        changed = False
        for production in grammar.production_order:
            before = len(first_sets[production.lhs])
            first_sets[production.lhs].update(_first_of_sequence(production.rhs, first_sets) - {EPSILON})
            if not production.rhs or EPSILON in _first_of_sequence(production.rhs, first_sets):
                first_sets[production.lhs].add(EPSILON)
            if len(first_sets[production.lhs]) != before:
                changed = True
    return first_sets


def _compute_follow(grammar: SLRGrammar) -> dict[str, set[str]]:
    first_sets = _compute_first(grammar)
    follow_sets: dict[str, set[str]] = {symbol: set() for symbol in grammar.nonterminals}
    follow_sets[grammar.start_symbol].add(ENDMARK)

    changed = True
    while changed:
        changed = False
        for production in grammar.production_order:
            rhs = production.rhs
            for index, symbol in enumerate(rhs):
                if symbol not in follow_sets:
                    continue
                beta = rhs[index + 1 :]
                first_beta = _first_of_sequence(beta, first_sets)
                before = len(follow_sets[symbol])
                follow_sets[symbol].update(first_beta - {EPSILON})
                if not beta or EPSILON in first_beta:
                    follow_sets[symbol].update(follow_sets[production.lhs])
                if len(follow_sets[symbol]) != before:
                    changed = True
    return follow_sets


def _first_of_sequence(sequence: tuple[str, ...], first_sets: dict[str, set[str]]) -> set[str]:
    if not sequence:
        return {EPSILON}

    result: set[str] = set()
    for symbol in sequence:
        symbol_first = first_sets.get(symbol, {symbol})
        result.update(symbol_first - {EPSILON})
        if EPSILON not in symbol_first:
            break
    else:
        result.add(EPSILON)
    return result


def _assign_table_entry(entries: dict[tuple[int, str], str], state: int, symbol: str, action: str) -> None:
    key = (state, symbol)
    existing = entries.get(key)
    if existing is None or existing == action:
        entries[key] = action
        return
    raise SLRTranslationError(
        f"该文法不是SLR(1)文法：分析表 M[{state}, {symbol}] 冲突，"
        f"{existing} 与 {action} 同时可用。"
    )


def _tokenize_expression(expression: str) -> list[_ExpressionToken]:
    if not expression.strip():
        raise SLRTranslationError("待分析表达式为空。")

    tokens: list[_ExpressionToken] = []
    index = 0
    while index < len(expression):
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char == ENDMARK:
            if any(not rest.isspace() for rest in expression[index + 1 :]):
                raise SLRTranslationError("结束符 # 后不能再出现其他输入。")
            break
        if char.isdigit():
            start = index
            while index < len(expression) and expression[index].isdigit():
                index += 1
            lexeme = expression[start:index]
            value = int(lexeme)
            tokens.append(_ExpressionToken("d", lexeme, value))
            continue
        if char in "+-*/()":
            tokens.append(_ExpressionToken(char, char))
            index += 1
            continue
        raise SLRTranslationError(f"表达式包含非法字符：{char}")

    if not tokens:
        raise SLRTranslationError("待分析表达式为空。")
    tokens.append(_ExpressionToken(ENDMARK, ENDMARK))
    return tokens


def _semantic_for_shift(token: _ExpressionToken) -> _SemanticValue:
    if token.symbol == "d":
        return _SemanticValue(token.symbol, token.lexeme, token.value)
    return _SemanticValue(token.symbol, token.lexeme)


def _apply_semantic_action(
    production: SLRProduction,
    rhs_values: list[_SemanticValue],
    quadruples: list[Quadruple],
    next_temp_index: int,
) -> tuple[_SemanticValue, int]:
    lhs = production.lhs
    rhs = production.rhs

    if (lhs, rhs) in {
        ("E", ("T",)),
        ("T", ("F",)),
        ("F", ("d",)),
    }:
        return _SemanticValue(lhs, rhs_values[0].place, rhs_values[0].value), next_temp_index

    if (lhs, rhs) == ("F", ("(", "E", ")")):
        return _SemanticValue(lhs, rhs_values[1].place, rhs_values[1].value), next_temp_index

    binary_ops = {
        ("E", ("E", "+", "T")): "+",
        ("E", ("E", "-", "T")): "-",
        ("T", ("T", "*", "F")): "*",
        ("T", ("T", "/", "F")): "/",
    }
    operator = binary_ops.get((lhs, rhs))
    if operator is None:
        raise SLRTranslationError(f"未实现产生式 {production.text} 的语义动作。")

    left = rhs_values[0]
    right = rhs_values[2]
    if left.value is None or right.value is None:
        raise SLRTranslationError(f"产生式 {production.text} 缺少可计算的语义值。")
    if operator == "/" and right.value == 0:
        raise SLRTranslationError("除数不能为 0。")

    result_value = _calculate(operator, left.value, right.value)
    temp_name = f"T{next_temp_index}"
    quadruples.append(Quadruple(len(quadruples) + 1, operator, left.place, right.place, temp_name))
    return _SemanticValue(lhs, temp_name, result_value), next_temp_index + 1


def _calculate(operator: str, left: Number, right: Number) -> Number:
    if operator == "+":
        return _normalize_number(left + right)
    if operator == "-":
        return _normalize_number(left - right)
    if operator == "*":
        return _normalize_number(left * right)
    if operator == "/":
        return _normalize_number(left / right)
    raise SLRTranslationError(f"未知运算符：{operator}")


def _failed_result(
    message: str,
    step_index: int,
    state_stack: list[int],
    symbol_stack: list[str],
    remaining_input: tuple[_ExpressionToken, ...] | list[_ExpressionToken],
    semantic_stack: list[_SemanticValue],
    steps: list[TranslationStep],
    quadruples: list[Quadruple],
) -> TranslationResult:
    steps.append(_make_step(step_index, state_stack, symbol_stack, remaining_input, message, "", semantic_stack))
    return TranslationResult(False, message, tuple(steps), tuple(quadruples), None, "")


def _make_step(
    index: int,
    state_stack: list[int],
    symbol_stack: list[str],
    remaining_input: tuple[_ExpressionToken, ...] | list[_ExpressionToken],
    action_text: str,
    goto_text: str,
    semantic_stack: list[_SemanticValue],
) -> TranslationStep:
    return TranslationStep(
        index=index,
        state_stack=", ".join(str(state) for state in state_stack),
        symbol_stack="".join(symbol_stack),
        input_text="".join(token.lexeme for token in remaining_input),
        action_text=action_text,
        goto_text=goto_text,
        semantic_stack=" ".join(value.display_text for value in semantic_stack),
    )


def _parse_state_action(action: str) -> int:
    try:
        return int(action[1:])
    except ValueError as exc:
        raise SLRTranslationError(f"非法移进动作：{action}") from exc


def _parse_reduce_action(action: str) -> int:
    try:
        return int(action[1:])
    except ValueError as exc:
        raise SLRTranslationError(f"非法归约动作：{action}") from exc


def _normalize_number(value: Number) -> Number:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _format_number(value: Number) -> str:
    normalized = _normalize_number(value)
    if isinstance(normalized, float):
        return f"{normalized:.10g}"
    return str(normalized)


def _looks_like_nonterminal(symbol: str) -> bool:
    return symbol.isascii() and symbol.isalpha() and symbol.isupper()
