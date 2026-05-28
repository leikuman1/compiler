from __future__ import annotations

import ctypes
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from compiler_project.core import DFAMinimizer, Determinizer, RegexParser, ThompsonBuilder
from compiler_project.io import AutomataCodec, DotExporter
from compiler_project.lexer import build_default_lexer


class CompilerCourseApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.geometry("1360x860")
        self.root.title("Python 词法分析与自动机实验系统 - 词法分析")
        self.project_root = Path(__file__).resolve().parents[2]

        self.codec = AutomataCodec()
        self.dot_exporter = DotExporter()
        self.regex_parser = RegexParser()
        self.thompson_builder = ThompsonBuilder()
        self.lexer = build_default_lexer()

        self.current_nfa = None
        self.current_dfa = None
        self.current_min_dfa = None

        self.preview_image: tk.PhotoImage | None = None
        self.automata_window: tk.Toplevel | None = None

        self.regex_var = tk.StringVar(value="(a|b)*abb")
        self.edit_mode = tk.BooleanVar(value=False)
        self.edit_status = tk.StringVar(value="当前：只读")
        self.module_status = tk.StringVar(value="当前模块：词法分析")
        self.lexer_status = tk.StringVar(value="词法分析程序已就绪")
        self.automata_status = tk.StringVar(value="请输入正规式后生成自动机")
        self.ll1_sentence_var = tk.StringVar()

        self.regex_entry: ttk.Entry | None = None
        self.source_text: tk.Text | None = None
        self.token_tree: ttk.Treeview | None = None
        self.error_tree: ttk.Treeview | None = None
        self.ll1_window: tk.Toplevel | None = None
        self.ll1_grammar_text: tk.Text | None = None
        self.ll1_first_tree: ttk.Treeview | None = None
        self.ll1_follow_tree: ttk.Treeview | None = None
        self.ll1_predict_tree: ttk.Treeview | None = None
        self.ll1_steps_tree: ttk.Treeview | None = None
        self.ll1_open_button: ttk.Button | None = None
        self.ll1_confirm_button: ttk.Button | None = None
        self.ll1_save_button: ttk.Button | None = None
        self.ll1_first_button: ttk.Button | None = None
        self.ll1_follow_button: ttk.Button | None = None
        self.ll1_build_table_button: ttk.Button | None = None
        self.ll1_one_step_display_button: ttk.Button | None = None
        self.ll1_single_step_button: ttk.Button | None = None
        self.ll1_exit_button: ttk.Button | None = None
        self.nfa_tree: ttk.Treeview | None = None
        self.dfa_tree: ttk.Treeview | None = None
        self.mfa_tree: ttk.Treeview | None = None
        self.nfa_start_var: tk.StringVar | None = None
        self.nfa_accept_var: tk.StringVar | None = None
        self.dfa_start_var: tk.StringVar | None = None
        self.dfa_accept_var: tk.StringVar | None = None
        self.mfa_start_var: tk.StringVar | None = None
        self.mfa_accept_var: tk.StringVar | None = None

        self._configure_fonts()
        self._build_layout()
        self._apply_edit_mode()

    def _configure_fonts(self) -> None:
        families = set(tkfont.families(self.root))
        ui_family = self._pick_font_family(
            families,
            ("Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun", "Arial"),
        )

        self.ui_font = tkfont.Font(family=ui_family, size=10)
        self.ui_bold_font = tkfont.Font(family=ui_family, size=10, weight="bold")
        self.text_font = tkfont.Font(family=ui_family, size=11)

        for name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkFixedFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                named_font = tkfont.nametofont(name)
            except tk.TclError:
                continue
            named_font.configure(family=ui_family, size=10)

        style = ttk.Style(self.root)
        style.configure(".", font=self.ui_font)
        style.configure("TButton", font=self.ui_font)
        style.configure("TMenubutton", font=self.ui_font)
        style.configure("TLabel", font=self.ui_font)
        style.configure("TLabelframe.Label", font=self.ui_bold_font)
        style.configure("Treeview", font=self.ui_font, rowheight=28)
        style.configure("Treeview.Heading", font=self.ui_bold_font)

    @staticmethod
    def _pick_font_family(families: set[str], candidates: tuple[str, ...]) -> str:
        for candidate in candidates:
            if candidate in families:
                return candidate
        return candidates[-1]

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True)

        top_bar = ttk.Frame(container)
        top_bar.pack(fill="x", padx=10, pady=(10, 0))
        self._build_function_bar(top_bar)

        self._build_lexer_page(container)

        status_bar = ttk.Frame(container)
        status_bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(status_bar, textvariable=self.module_status).pack(side="left")
        ttk.Label(status_bar, textvariable=self.edit_status).pack(side="left", padx=(18, 0))
        ttk.Label(status_bar, textvariable=self.lexer_status).pack(side="left", padx=(18, 0))

    def _build_function_bar(self, parent: ttk.Frame) -> None:
        self.file_button = ttk.Menubutton(parent, text="文件")
        self.file_button.pack(side="left", padx=(0, 8))
        file_menu = tk.Menu(self.file_button, tearoff=False, font=self.ui_font)
        file_menu.add_command(label="打开源码文件", command=self.load_source_file)
        file_menu.add_command(label="填充课程样例", command=self.load_sample_source)
        file_menu.add_command(label="清空编辑区", command=self.clear_source_text)
        file_menu.add_separator()
        file_menu.add_command(label="退出程序", command=self.root.destroy)
        self.file_button["menu"] = file_menu

        self.edit_button = ttk.Button(parent, text="编辑", command=self.toggle_edit_mode)
        self.edit_button.pack(side="left", padx=8)

        self.compile_button = ttk.Menubutton(parent, text="编译")
        self.compile_button.pack(side="left", padx=8)
        compile_menu = tk.Menu(self.compile_button, tearoff=False, font=self.ui_font)
        compile_menu.add_command(label="词法分析程序(A)", command=self.run_lexer)
        compile_menu.add_command(label="NFA_DFA_MFA(N)", command=self.open_automata_window)
        compile_menu.add_command(label="LL(1)预测分析(P)", command=self.open_ll1_window)
        self.compile_button["menu"] = compile_menu

    def _build_lexer_page(self, parent: ttk.Frame) -> None:
        content = ttk.PanedWindow(parent, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10, pady=10)

        editor_frame = ttk.LabelFrame(content, text="编辑区")
        content.add(editor_frame, weight=3)
        editor_frame.rowconfigure(1, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        editor_actions = ttk.Frame(editor_frame)
        editor_actions.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        ttk.Button(editor_actions, text="打开源码", command=self.load_source_file).pack(side="left", padx=(0, 6))
        ttk.Button(editor_actions, text="填充样例", command=self.load_sample_source).pack(side="left", padx=6)
        ttk.Button(editor_actions, text="开始词法分析", command=self.run_lexer).pack(side="left", padx=6)

        source_frame = ttk.Frame(editor_frame)
        source_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        source_frame.rowconfigure(0, weight=1)
        source_frame.columnconfigure(0, weight=1)

        self.source_text = tk.Text(source_frame, font=self.text_font, wrap="none")
        self.source_text.grid(row=0, column=0, sticky="nsew")

        source_y = ttk.Scrollbar(source_frame, orient="vertical", command=self.source_text.yview)
        source_y.grid(row=0, column=1, sticky="ns")
        source_x = ttk.Scrollbar(source_frame, orient="horizontal", command=self.source_text.xview)
        source_x.grid(row=1, column=0, sticky="ew")
        self.source_text.configure(yscrollcommand=source_y.set, xscrollcommand=source_x.set)

        right_split = ttk.PanedWindow(content, orient="vertical")
        content.add(right_split, weight=2)

        token_frame = ttk.LabelFrame(right_split, text="Token 分析区")
        error_frame = ttk.LabelFrame(right_split, text="错误信息区")
        right_split.add(token_frame, weight=1)
        right_split.add(error_frame, weight=1)

        self.token_tree = self._build_result_tree(
            token_frame,
            (
                ("type", "类别", 120),
                ("lexeme", "词素", 220),
                ("line", "行", 60),
                ("column", "列", 60),
            ),
        )
        self.error_tree = self._build_result_tree(
            error_frame,
            (
                ("message", "错误", 180),
                ("lexeme", "片段", 180),
                ("line", "行", 60),
                ("column", "列", 60),
            ),
        )

    def _build_result_tree(
        self,
        parent: ttk.LabelFrame,
        columns: tuple[tuple[str, str, int], ...],
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=tuple(item[0] for item in columns), show="headings")
        for key, title_text, width in columns:
            tree.heading(key, text=title_text)
            tree.column(key, width=width, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        return tree

    def open_automata_window(self) -> None:
        if self.automata_window is not None and self.automata_window.winfo_exists():
            self.automata_window.deiconify()
            self.automata_window.lift()
            self.automata_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title("NFA_DFA_MFA")
        window.geometry("1320x780")
        window.protocol("WM_DELETE_WINDOW", self._close_automata_window)
        self.automata_window = window
        self._apply_widget_font(window)

        container = ttk.Frame(window, padding=10)
        container.pack(fill="both", expand=True)

        expression_frame = ttk.LabelFrame(container, text="表达式")
        expression_frame.pack(fill="x", pady=(0, 10))

        expression_row = ttk.Frame(expression_frame)
        expression_row.pack(fill="x", padx=10, pady=10)
        ttk.Label(expression_row, text="请输入一个正规式：").pack(side="left")
        self.regex_entry = ttk.Entry(expression_row, textvariable=self.regex_var, width=42)
        self.regex_entry.pack(side="left", padx=(8, 16))
        ttk.Label(expression_row, text="例如：(a*|b)*").pack(side="left")
        ttk.Button(expression_row, text="验证正规式", command=self.validate_regex).pack(side="right")
        ttk.Button(expression_row, text="退出", command=self._close_automata_window).pack(side="right", padx=(0, 8))

        ttk.Label(expression_frame, textvariable=self.automata_status).pack(anchor="w", padx=10, pady=(0, 10))

        panels = ttk.Frame(container)
        panels.pack(fill="both", expand=True)
        for column in range(3):
            panels.columnconfigure(column, weight=1, uniform="automata")
        panels.rowconfigure(0, weight=1)

        (
            self.nfa_tree,
            self.nfa_start_var,
            self.nfa_accept_var,
            nfa_button_bar,
        ) = self._build_automata_panel(panels, 0, "正规式 -> NFA")
        ttk.Button(nfa_button_bar, text="读入NFA文件", command=self.load_nfa_file).pack(side="left", padx=4)
        ttk.Button(nfa_button_bar, text="生成NFA", command=self.generate_nfa).pack(side="left", padx=4)
        ttk.Button(nfa_button_bar, text="保存为NFA文件", command=self.save_current_nfa).pack(side="left", padx=4)

        (
            self.dfa_tree,
            self.dfa_start_var,
            self.dfa_accept_var,
            dfa_button_bar,
        ) = self._build_automata_panel(panels, 1, "NFA -> DFA")
        ttk.Button(dfa_button_bar, text="读入DFA文件", command=self.load_dfa_file).pack(side="left", padx=4)
        ttk.Button(dfa_button_bar, text="生成DFA", command=self.generate_dfa).pack(side="left", padx=4)
        ttk.Button(dfa_button_bar, text="保存为DFA文件", command=self.save_current_dfa).pack(side="left", padx=4)

        (
            self.mfa_tree,
            self.mfa_start_var,
            self.mfa_accept_var,
            mfa_button_bar,
        ) = self._build_automata_panel(panels, 2, "DFA -> MFA")
        ttk.Button(mfa_button_bar, text="生成MFA", command=self.generate_mfa).pack(side="left", padx=4)

        self._apply_edit_mode()
        self._refresh_all_automata_panels()

    def _build_automata_panel(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
    ) -> tuple[ttk.Treeview, tk.StringVar, tk.StringVar, ttk.Frame]:
        panel = ttk.LabelFrame(parent, text=title)
        panel.grid(row=0, column=column, sticky="nsew", padx=6)
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)

        tree_frame = ttk.Frame(panel)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 8))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        tree = ttk.Treeview(
            tree_frame,
            columns=("source", "symbol", "target"),
            show="headings",
            height=20,
        )
        for key, title_text, width in (
            ("source", "起始状态", 110),
            ("symbol", "接受符号", 110),
            ("target", "到达状态", 110),
        ):
            tree.heading(key, text=title_text)
            tree.column(key, width=width, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        info_frame = ttk.Frame(panel)
        info_frame.grid(row=1, column=0, sticky="ew", padx=10)
        start_var = tk.StringVar(value="开始状态集：")
        accept_var = tk.StringVar(value="终结状态集：")
        ttk.Label(info_frame, textvariable=start_var).pack(anchor="w", pady=(0, 4))
        ttk.Label(info_frame, textvariable=accept_var).pack(anchor="w")

        button_bar = ttk.Frame(panel)
        button_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(10, 12))
        return tree, start_var, accept_var, button_bar

    def open_ll1_window(self) -> None:
        if self.ll1_window is not None and self.ll1_window.winfo_exists():
            self.ll1_window.deiconify()
            self.ll1_window.lift()
            self.ll1_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title("LL(1)预测分析")
        window.geometry("1320x780")
        window.protocol("WM_DELETE_WINDOW", self._close_ll1_window)
        self.ll1_window = window

        self._build_ll1_layout(window)
        self._apply_widget_font(window)

    def _build_ll1_layout(self, window: tk.Toplevel) -> None:
        container = ttk.Frame(window, padding=10)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=4, minsize=420)
        container.columnconfigure(1, weight=6, minsize=760)
        container.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(container)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=3)
        left_panel.rowconfigure(1, weight=2)
        left_panel.rowconfigure(2, weight=0)
        left_panel.rowconfigure(3, weight=2)

        right_panel = ttk.Frame(container)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=3)
        right_panel.rowconfigure(1, weight=4)

        self._build_ll1_left_panel(left_panel)
        self._build_ll1_right_panel(right_panel)

    def _build_ll1_left_panel(self, parent: ttk.Frame) -> None:
        grammar_frame = ttk.LabelFrame(parent, text="原始文法")
        grammar_frame.grid(row=0, column=0, sticky="nsew")
        grammar_frame.columnconfigure(0, weight=1)
        grammar_frame.rowconfigure(2, weight=1)

        actions = ttk.Frame(grammar_frame)
        actions.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        self.ll1_open_button = ttk.Button(actions, text="打开文件")
        self.ll1_open_button.pack(side="left", padx=(0, 6))
        self.ll1_confirm_button = ttk.Button(actions, text="确认文法")
        self.ll1_confirm_button.pack(side="left", padx=6)
        self.ll1_save_button = ttk.Button(actions, text="保存文件")
        self.ll1_save_button.pack(side="left", padx=6)

        ttk.Label(
            grammar_frame,
            text="请输入形如E->ab的LL1文法，其中的空字符用$代替",
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

        grammar_text_frame = ttk.Frame(grammar_frame)
        grammar_text_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        grammar_text_frame.rowconfigure(0, weight=1)
        grammar_text_frame.columnconfigure(0, weight=1)

        self.ll1_grammar_text = tk.Text(grammar_text_frame, font=self.text_font, wrap="none", height=12)
        self.ll1_grammar_text.grid(row=0, column=0, sticky="nsew")

        grammar_y = ttk.Scrollbar(grammar_text_frame, orient="vertical", command=self.ll1_grammar_text.yview)
        grammar_y.grid(row=0, column=1, sticky="ns")
        grammar_x = ttk.Scrollbar(grammar_text_frame, orient="horizontal", command=self.ll1_grammar_text.xview)
        grammar_x.grid(row=1, column=0, sticky="ew")
        self.ll1_grammar_text.configure(yscrollcommand=grammar_y.set, xscrollcommand=grammar_x.set)

        first_container, self.ll1_first_tree = self._build_ll1_placeholder_tree(
            parent,
            "FIRST集",
            (
                ("symbol", "非终结符", 110),
                ("result", "结果", 220),
            ),
        )
        first_container.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        first_follow_actions = ttk.Frame(parent)
        first_follow_actions.grid(row=2, column=0, sticky="w", pady=10)
        self.ll1_first_button = ttk.Button(first_follow_actions, text="求First集")
        self.ll1_first_button.pack(side="left", padx=(0, 8))
        self.ll1_follow_button = ttk.Button(first_follow_actions, text="求Follow集")
        self.ll1_follow_button.pack(side="left")

        follow_container, self.ll1_follow_tree = self._build_ll1_placeholder_tree(
            parent,
            "FOLLOW集",
            (
                ("symbol", "非终结符", 110),
                ("result", "结果", 220),
            ),
        )
        follow_container.grid(row=3, column=0, sticky="nsew")

        for button in (
            self.ll1_open_button,
            self.ll1_confirm_button,
            self.ll1_save_button,
            self.ll1_first_button,
            self.ll1_follow_button,
        ):
            if button is not None:
                button.state(["disabled"])

    def _build_ll1_right_panel(self, parent: ttk.Frame) -> None:
        predict_frame = ttk.LabelFrame(parent, text="预测分析表")
        predict_frame.grid(row=0, column=0, sticky="nsew")
        predict_frame.columnconfigure(0, weight=1)
        predict_frame.rowconfigure(1, weight=1)

        predict_actions = ttk.Frame(predict_frame)
        predict_actions.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        self.ll1_build_table_button = ttk.Button(predict_actions, text="构造预测分析表")
        self.ll1_build_table_button.pack(side="left")
        self.ll1_exit_button = ttk.Button(predict_actions, text="退出", command=self._close_ll1_window)
        self.ll1_exit_button.pack(side="right")

        predict_container, self.ll1_predict_tree = self._build_ll1_placeholder_tree(
            predict_frame,
            None,
            (
                ("nonterminal", "非终结符", 120),
                ("terminal_1", "终结符1", 140),
                ("terminal_2", "终结符2", 140),
                ("terminal_3", "终结符3", 140),
                ("terminal_4", "终结符4", 140),
            ),
            xscroll=True,
        )
        predict_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        analysis_frame = ttk.LabelFrame(parent, text="句子分析")
        analysis_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        analysis_frame.columnconfigure(0, weight=1)
        analysis_frame.rowconfigure(2, weight=1)

        sentence_row = ttk.Frame(analysis_frame)
        sentence_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        sentence_row.columnconfigure(1, weight=1)
        ttk.Label(sentence_row, text="分析句子").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(sentence_row, textvariable=self.ll1_sentence_var).grid(row=0, column=1, sticky="ew")

        step_actions = ttk.Frame(analysis_frame)
        step_actions.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))
        self.ll1_one_step_display_button = ttk.Button(step_actions, text="一步显示")
        self.ll1_one_step_display_button.pack(side="left", padx=(0, 8))
        self.ll1_single_step_button = ttk.Button(step_actions, text="单步显示")
        self.ll1_single_step_button.pack(side="left")

        steps_container, self.ll1_steps_tree = self._build_ll1_placeholder_tree(
            analysis_frame,
            None,
            (
                ("step", "步骤序号", 110),
                ("stack", "符号栈", 180),
                ("input", "输入串", 180),
                ("production", "所用产生式", 280),
            ),
            xscroll=True,
        )
        steps_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.ll1_build_table_button.state(["disabled"])
        self.ll1_one_step_display_button.state(["disabled"])
        self.ll1_single_step_button.state(["disabled"])

    def _build_ll1_placeholder_tree(
        self,
        parent: ttk.Frame,
        title: str | None,
        columns: tuple[tuple[str, str, int], ...],
        *,
        xscroll: bool = False,
    ) -> tuple[ttk.Widget, ttk.Treeview]:
        container: ttk.Widget
        if title is None:
            container = ttk.Frame(parent)
        else:
            container = ttk.LabelFrame(parent, text=title)

        frame = ttk.Frame(container)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=tuple(item[0] for item in columns), show="headings")
        for key, heading_text, width in columns:
            tree.heading(key, text=heading_text)
            tree.column(key, width=width, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=y_scroll.set)

        if xscroll:
            x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
            x_scroll.grid(row=1, column=0, sticky="ew")
            tree.configure(xscrollcommand=x_scroll.set)

        return container, tree

    def _close_automata_window(self) -> None:
        if self.automata_window is not None and self.automata_window.winfo_exists():
            self.automata_window.destroy()
        self.automata_window = None
        self.regex_entry = None
        self.nfa_tree = None
        self.dfa_tree = None
        self.mfa_tree = None
        self.nfa_start_var = None
        self.nfa_accept_var = None
        self.dfa_start_var = None
        self.dfa_accept_var = None
        self.mfa_start_var = None
        self.mfa_accept_var = None

    def _close_ll1_window(self) -> None:
        if self.ll1_window is not None and self.ll1_window.winfo_exists():
            self.ll1_window.destroy()
        self.ll1_window = None
        self.ll1_grammar_text = None
        self.ll1_first_tree = None
        self.ll1_follow_tree = None
        self.ll1_predict_tree = None
        self.ll1_steps_tree = None
        self.ll1_open_button = None
        self.ll1_confirm_button = None
        self.ll1_save_button = None
        self.ll1_first_button = None
        self.ll1_follow_button = None
        self.ll1_build_table_button = None
        self.ll1_one_step_display_button = None
        self.ll1_single_step_button = None
        self.ll1_exit_button = None
        self.ll1_sentence_var.set("")

    def toggle_edit_mode(self) -> None:
        self.edit_mode.set(not self.edit_mode.get())
        self._apply_edit_mode()

    def _apply_edit_mode(self) -> None:
        editable = self.edit_mode.get()
        if self.source_text is not None:
            self.source_text.configure(state="normal" if editable else "disabled")
        self.edit_button.configure(text="完成编辑" if editable else "编辑")
        self.edit_status.set("当前：可编辑" if editable else "当前：只读")

    def validate_regex(self) -> None:
        try:
            self.regex_parser.parse(self.regex_var.get().strip())
            success_message = "正规式验证通过，可以继续生成 NFA / DFA / MFA。"
            self.automata_status.set(success_message)
            messagebox.showinfo("验证结果", success_message)
        except Exception as exc:
            self.automata_status.set("正规式验证失败，请检查输入后重试")
            messagebox.showerror("正规式错误", str(exc))

    def generate_nfa(self) -> None:
        self.open_automata_window()
        pattern = self.regex_var.get().strip()
        try:
            regex_ir = self.regex_parser.parse(pattern)
            self.current_nfa = self.thompson_builder.build(regex_ir)
            self.current_dfa = None
            self.current_min_dfa = None
            self._refresh_nfa_panel()
            self._clear_dfa_panel()
            self._clear_mfa_panel()
            self.automata_status.set("已根据正规式生成 NFA")
        except Exception as exc:
            messagebox.showerror("生成 NFA 失败", str(exc))

    def generate_dfa(self) -> None:
        self.open_automata_window()
        if self.current_nfa is None:
            self.generate_nfa()
        if self.current_nfa is None:
            return
        try:
            self.current_dfa = Determinizer.convert(self.current_nfa)
            self.current_min_dfa = None
            self._refresh_dfa_panel()
            self._clear_mfa_panel()
            self.automata_status.set("已根据当前 NFA 生成 DFA")
        except Exception as exc:
            messagebox.showerror("生成 DFA 失败", str(exc))

    def generate_mfa(self) -> None:
        self.open_automata_window()
        if self.current_dfa is None:
            self.generate_dfa()
        if self.current_dfa is None:
            return
        try:
            self.current_min_dfa = DFAMinimizer.minimize(self.current_dfa)
            self._refresh_mfa_panel()
            self.automata_status.set("已先去除 DFA 冗余状态，再生成 MFA")
        except Exception as exc:
            messagebox.showerror("生成 MFA 失败", str(exc))

    def load_nfa_file(self) -> None:
        self.open_automata_window()
        path = filedialog.askopenfilename(
            title="选择 NFA 文件",
            filetypes=[("NFA 文件", "*.nfa"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            self.current_nfa = self.codec.load_nfa(path)
            self.current_dfa = None
            self.current_min_dfa = None
            self._refresh_nfa_panel()
            self._clear_dfa_panel()
            self._clear_mfa_panel()
            self.automata_status.set(f"已读入 NFA 文件：{path}")
        except Exception as exc:
            messagebox.showerror("读取 NFA 失败", str(exc))

    def load_dfa_file(self) -> None:
        self.open_automata_window()
        path = filedialog.askopenfilename(
            title="选择 DFA 文件",
            filetypes=[("DFA 文件", "*.dfa"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            self.current_nfa = None
            self.current_dfa = self.codec.load_dfa(path)
            self.current_min_dfa = None
            self._clear_nfa_panel()
            self._refresh_dfa_panel()
            self._clear_mfa_panel()
            self.automata_status.set(f"已读入 DFA 文件：{path}")
        except Exception as exc:
            messagebox.showerror("读取 DFA 失败", str(exc))

    def save_current_nfa(self) -> None:
        if self.current_nfa is None:
            messagebox.showwarning("暂无 NFA", "请先生成或读入 NFA。")
            return
        path = filedialog.asksaveasfilename(
            title="保存 NFA",
            defaultextension=".nfa",
            filetypes=[("NFA 文件", "*.nfa"), ("所有文件", "*.*")],
        )
        if not path:
            return
        self.codec.save_nfa(self.current_nfa, path)
        self.automata_status.set(f"NFA 已保存到：{path}")

    def save_current_dfa(self) -> None:
        if self.current_dfa is None:
            messagebox.showwarning("暂无 DFA", "请先生成或读入 DFA。")
            return
        path = filedialog.asksaveasfilename(
            title="保存 DFA",
            defaultextension=".dfa",
            filetypes=[("DFA 文件", "*.dfa"), ("所有文件", "*.*")],
        )
        if not path:
            return
        self.codec.save_dfa(self.current_dfa, path)
        self.automata_status.set(f"DFA 已保存到：{path}")

    def export_current_graph(self) -> None:
        automaton = self.current_min_dfa or self.current_dfa or self.current_nfa
        if automaton is None:
            messagebox.showwarning("暂无自动机", "请先生成或读入自动机。")
            return

        path = filedialog.asksaveasfilename(
            title="导出自动机图",
            defaultextension=".dot",
            filetypes=[("DOT 文件", "*.dot"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            self.dot_exporter.export(automaton, path)
            if self.dot_exporter.is_dot_available():
                png_path = str(Path(path).with_suffix(".png"))
                self.dot_exporter.render_png(path, png_path)
                self._show_graph_preview(png_path)
                self.automata_status.set(f"已导出 DOT/PNG：{path}")
            else:
                self.automata_status.set(f"已导出 DOT：{path}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def _show_graph_preview(self, png_path: str) -> None:
        preview_window = tk.Toplevel(self.root)
        preview_window.title("自动机图预览")
        self.preview_image = tk.PhotoImage(file=png_path)
        ttk.Label(preview_window, image=self.preview_image).pack(fill="both", expand=True)

    def _refresh_all_automata_panels(self) -> None:
        self._refresh_nfa_panel()
        self._refresh_dfa_panel()
        self._refresh_mfa_panel()

    def _refresh_nfa_panel(self) -> None:
        if self.nfa_tree is None or self.nfa_start_var is None or self.nfa_accept_var is None:
            return
        if self.current_nfa is None:
            self._clear_nfa_panel()
            return
        self._populate_nfa_tree(self.nfa_tree, self.current_nfa)
        self.nfa_start_var.set(f"开始状态集：{self._format_states({self.current_nfa.start_state})}")
        self.nfa_accept_var.set(f"终结状态集：{self._format_states(self.current_nfa.accept_states)}")

    def _refresh_dfa_panel(self) -> None:
        if self.dfa_tree is None or self.dfa_start_var is None or self.dfa_accept_var is None:
            return
        if self.current_dfa is None:
            self._clear_dfa_panel()
            return
        self._populate_dfa_tree(self.dfa_tree, self.current_dfa)
        self.dfa_start_var.set(f"开始状态集：{self._format_states({self.current_dfa.start_state})}")
        self.dfa_accept_var.set(f"终结状态集：{self._format_states(self.current_dfa.accept_states)}")

    def _refresh_mfa_panel(self) -> None:
        if self.mfa_tree is None or self.mfa_start_var is None or self.mfa_accept_var is None:
            return
        if self.current_min_dfa is None:
            self._clear_mfa_panel()
            return
        self._populate_dfa_tree(self.mfa_tree, self.current_min_dfa)
        self.mfa_start_var.set(f"开始状态集：{self._format_states({self.current_min_dfa.start_state})}")
        self.mfa_accept_var.set(f"终结状态集：{self._format_states(self.current_min_dfa.accept_states)}")

    def _clear_nfa_panel(self) -> None:
        if self.nfa_tree is not None:
            self._clear_tree(self.nfa_tree)
        if self.nfa_start_var is not None:
            self.nfa_start_var.set("开始状态集：")
        if self.nfa_accept_var is not None:
            self.nfa_accept_var.set("终结状态集：")

    def _clear_dfa_panel(self) -> None:
        if self.dfa_tree is not None:
            self._clear_tree(self.dfa_tree)
        if self.dfa_start_var is not None:
            self.dfa_start_var.set("开始状态集：")
        if self.dfa_accept_var is not None:
            self.dfa_accept_var.set("终结状态集：")

    def _clear_mfa_panel(self) -> None:
        if self.mfa_tree is not None:
            self._clear_tree(self.mfa_tree)
        if self.mfa_start_var is not None:
            self.mfa_start_var.set("开始状态集：")
        if self.mfa_accept_var is not None:
            self.mfa_accept_var.set("终结状态集：")

    def _populate_nfa_tree(self, tree: ttk.Treeview, automaton) -> None:
        self._clear_tree(tree)
        rows: list[tuple[int, str, int]] = []
        for source in sorted(automaton.transitions):
            for symbol in sorted(automaton.transitions[source], key=self._sort_symbol):
                for target in sorted(automaton.transitions[source][symbol]):
                    rows.append((source, self._display_symbol(symbol), target))
        for row in rows:
            tree.insert("", "end", values=row)

    def _populate_dfa_tree(self, tree: ttk.Treeview, automaton) -> None:
        self._clear_tree(tree)
        rows: list[tuple[int, str, int]] = []
        for source in sorted(automaton.transitions):
            for symbol, target in sorted(
                automaton.transitions[source].items(),
                key=lambda item: self._sort_symbol(item[0]),
            ):
                rows.append((source, self._display_symbol(symbol), target))
        for row in rows:
            tree.insert("", "end", values=row)

    def load_source_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 C 源文件",
            filetypes=[("文本文件", "*.txt;*.c"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            text = self.codec.read_text_file(path)
            self._set_text(self.source_text, text)
            self.lexer_status.set(f"已载入源文件：{path}")
        except Exception as exc:
            messagebox.showerror("读取失败", str(exc))

    def load_sample_source(self) -> None:
        sample_path = self.project_root / "Ctest.txt"
        if sample_path.exists():
            try:
                text = self.codec.read_text_file(sample_path)
                marker = "--------源程序"
                if marker in text:
                    text = text.split(marker, 1)[1]
                    if "--------词法分析结果" in text:
                        text = text.split("--------词法分析结果", 1)[0]
                    text = text.strip()
                self._set_text(self.source_text, text)
                self.lexer_status.set("已填充课程样例")
                return
            except Exception:
                pass
        self._set_text(self.source_text, "int ab,a12,2a1;\nfor(ab=0;ab<=10.5;ab++)\n    a12=a21+1000;")
        self.lexer_status.set("已填充默认样例")

    def clear_source_text(self) -> None:
        self._set_text(self.source_text, "")
        self.lexer_status.set("编辑区已清空")

    def run_lexer(self) -> None:
        source = self.source_text.get("1.0", "end-1c") if self.source_text is not None else ""
        tokens, errors = self.lexer.scan(source)

        if self.token_tree is not None:
            self._clear_tree(self.token_tree)
        if self.error_tree is not None:
            self._clear_tree(self.error_tree)

        if self.token_tree is not None:
            for token in tokens:
                self.token_tree.insert("", "end", values=(token.type, token.lexeme, token.line, token.column))
        if self.error_tree is not None:
            for error in errors:
                self.error_tree.insert("", "end", values=(error.message, error.lexeme, error.line, error.column))

        self.lexer_status.set(f"词法分析完成：{len(tokens)} 个 token，{len(errors)} 个错误")

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    @staticmethod
    def _format_states(states: set[int]) -> str:
        if not states:
            return "{}"
        return "{" + ", ".join(str(state) for state in sorted(states)) + "}"

    @staticmethod
    def _display_symbol(symbol: str) -> str:
        mapping = {"\n": r"\n", "\t": r"\t", "\r": r"\r", " ": r"\s"}
        return mapping.get(symbol, symbol)

    @staticmethod
    def _sort_symbol(symbol: str) -> tuple[int, str]:
        if symbol == "#":
            return (0, symbol)
        return (1, symbol)

    @staticmethod
    def _set_text(widget: tk.Text | None, text: str) -> None:
        if widget is None:
            return
        original_state = str(widget.cget("state"))
        if original_state == "disabled":
            widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        if original_state == "disabled":
            widget.configure(state="disabled")

    def _apply_widget_font(self, widget: tk.Misc) -> None:
        try:
            widget.configure(font=self.ui_font)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._apply_widget_font(child)


def enable_windows_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def main() -> None:
    enable_windows_dpi_awareness()
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = CompilerCourseApp(root)
    _ = app
    root.mainloop()
