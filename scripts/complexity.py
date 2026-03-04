"""
Vitals — Code complexity analysis.

Language-agnostic structural analysis. No regex. No hardcoded language lists.

Two modes:
  - Python files: AST-based (precise function/branch/nesting detection)
  - All other files: Indentation-based (measures nesting depth from whitespace)

The indentation-based approach is validated by CodeScene's research:
nesting depth is the strongest single predictor of defect density.
We don't need to identify keywords — we measure structure.
"""

import ast
import os
from collections import Counter


class ComplexityResult:
    """Result of complexity analysis for a single file."""

    def __init__(self, file_path, total_lines=0, code_lines=0,
                 max_nesting_depth=0, deep_nesting_lines=0,
                 function_count=0, avg_function_length=0,
                 longest_function_lines=0, branch_count=0):
        self.file_path = file_path
        self.total_lines = total_lines
        self.code_lines = code_lines
        self.max_nesting_depth = max_nesting_depth
        self.deep_nesting_lines = deep_nesting_lines  # lines at depth >= 3
        self.function_count = function_count
        self.avg_function_length = avg_function_length
        self.longest_function_lines = longest_function_lines
        self.branch_count = branch_count

    @property
    def score(self):
        """
        Complexity score (0-100). Higher = more complex = worse.

        Gate: files with max nesting <= 1 score 0 — they're flat data
        (lock files, configs, prose), not structured code.

        For files with real structure (nesting >= 2), score is driven by:
        - Nesting depth (strongest predictor per CodeScene research)
        - Deep-nesting density (proportion of code at depth >= 3)
        - Longest logical section
        - Branch count (from AST for Python)
        """
        # Gate: shallow nesting = not complex code. Files with nesting <= 2
        # are flat data (lock files, CSVs), configs (TOML, YAML), or prose
        # (markdown, docs). Real source code with logic has nesting >= 3.
        # This eliminates noise without any hardcoded file type list.
        if self.max_nesting_depth <= 2:
            return 0

        nesting_score = min(self.max_nesting_depth * 8, 35)

        if self.code_lines > 0:
            deep_ratio = self.deep_nesting_lines / self.code_lines
            deep_score = min(deep_ratio * 100, 25)
        else:
            deep_score = 0

        longest_score = min(self.longest_function_lines * 0.12, 20)
        branch_score = min(self.branch_count * 0.3, 10)

        # File length only counts when there's real structure
        line_score = min(self.total_lines * 0.005, 10)

        total = nesting_score + deep_score + longest_score + line_score + branch_score
        return min(100, round(total))


def compute_complexity(file_path, repo_root=None):
    """Compute complexity metrics for a single file."""
    abs_path = file_path
    if repo_root and not os.path.isabs(file_path):
        abs_path = os.path.join(repo_root, file_path)

    if not os.path.isfile(abs_path):
        return ComplexityResult(file_path)

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (IOError, OSError):
        return ComplexityResult(file_path)

    if not content.strip():
        return ComplexityResult(file_path)

    # Try Python AST first (works for .py files, fails fast for others)
    if file_path.endswith(".py"):
        result = _try_python_ast(file_path, content)
        if result is not None:
            return result

    # Universal: indentation-based structural analysis
    return _analyze_by_indentation(file_path, content)


def _try_python_ast(file_path, content):
    """
    Analyze Python file using the ast module.
    Returns None if parsing fails (caller should use indentation analysis).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    lines = content.splitlines()
    total_lines = len(lines)
    code_lines = sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))

    functions = []
    max_nesting = 0
    branch_count = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try,
                             ast.With, ast.ExceptHandler)):
            branch_count += 1
        if isinstance(node, ast.BoolOp):
            branch_count += len(node.values) - 1

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = _get_node_line_count(node)
            functions.append(func_lines)
            nesting = _get_max_nesting(node)
            max_nesting = max(max_nesting, nesting)

    function_count = len(functions)
    avg_func_length = sum(functions) / len(functions) if functions else 0
    longest_func = max(functions) if functions else 0

    # Count deep-nesting lines via indentation (even for Python)
    deep_nesting_lines = _count_deep_nesting_lines(lines)

    return ComplexityResult(
        file_path=file_path,
        total_lines=total_lines,
        code_lines=code_lines,
        max_nesting_depth=max_nesting,
        deep_nesting_lines=deep_nesting_lines,
        function_count=function_count,
        avg_function_length=round(avg_func_length),
        longest_function_lines=longest_func,
        branch_count=branch_count,
    )


def _get_node_line_count(node):
    """Get the number of lines a node spans."""
    if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
        return node.end_lineno - node.lineno + 1
    return 0


def _get_max_nesting(node, depth=0):
    """Get the maximum nesting depth within a node."""
    max_depth = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.Try,
                              ast.With, ast.ExceptHandler,
                              ast.FunctionDef, ast.AsyncFunctionDef)):
            child_depth = _get_max_nesting(child, depth + 1)
        else:
            child_depth = _get_max_nesting(child, depth)
        max_depth = max(max_depth, child_depth)
    return max_depth


# ---------------------------------------------------------------------------
# Universal Indentation-Based Analysis
# ---------------------------------------------------------------------------

def _analyze_by_indentation(file_path, content):
    """
    Language-agnostic complexity analysis using only indentation structure.

    Measures:
      - Nesting depth from whitespace (works for any language)
      - Proportion of code at deep nesting levels
      - Logical sections (indentation transitions as proxy for function boundaries)
      - Total size

    No regex. No keyword detection. No language-specific logic.
    """
    lines = content.splitlines()
    total_lines = len(lines)

    # Detect indentation unit (tab vs spaces, and how many spaces per level)
    indent_unit = _detect_indent_unit(lines)

    code_lines = 0
    max_nesting = 0
    deep_nesting_lines = 0
    nesting_levels = []

    # Track logical sections (top-level blocks as proxy for functions)
    section_starts = []
    prev_level = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        code_lines += 1

        # Compute nesting level
        raw_indent = len(line) - len(line.lstrip())
        if indent_unit > 0:
            level = raw_indent // indent_unit
        else:
            level = 0

        nesting_levels.append(level)
        max_nesting = max(max_nesting, level)

        if level >= 3:
            deep_nesting_lines += 1

        # Detect section boundaries: transitions from indented back to level 0 or 1
        if level <= 1 and prev_level > 1:
            section_starts.append(i)
        elif prev_level == -1 or (level == 0 and prev_level >= 0 and i > 0):
            if prev_level == -1:
                section_starts.append(i)

        prev_level = level

    # Estimate function count from section boundaries
    function_count = max(1, len(section_starts)) if section_starts else 0

    # Estimate function lengths from section boundaries
    function_lengths = []
    for idx, start in enumerate(section_starts):
        if idx + 1 < len(section_starts):
            length = section_starts[idx + 1] - start
        else:
            length = total_lines - start
        if length > 0:
            function_lengths.append(length)

    avg_func_length = sum(function_lengths) / len(function_lengths) if function_lengths else 0
    longest_func = max(function_lengths) if function_lengths else 0

    return ComplexityResult(
        file_path=file_path,
        total_lines=total_lines,
        code_lines=code_lines,
        max_nesting_depth=max_nesting,
        deep_nesting_lines=deep_nesting_lines,
        function_count=function_count,
        avg_function_length=round(avg_func_length),
        longest_function_lines=longest_func,
        branch_count=0,  # Not available without language-specific parsing
    )


def _detect_indent_unit(lines):
    """
    Detect the indentation unit (number of spaces per level) from the file.
    Returns the most common indentation increment, or 4 as a sensible default.
    """
    increments = []
    prev_indent = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Handle tabs: each tab = 1 unit
        if line and line[0] == "\t":
            indent = len(line) - len(line.lstrip("\t"))
            if indent > prev_indent and indent - prev_indent > 0:
                increments.append(1)  # Tab-based: 1 tab = 1 level
            prev_indent = indent
            continue

        # Handle spaces
        indent = len(line) - len(line.lstrip(" "))
        if indent > prev_indent:
            diff = indent - prev_indent
            if 0 < diff <= 8:
                increments.append(diff)
        prev_indent = indent

    if not increments:
        return 4  # sensible default

    counts = Counter(increments)
    return counts.most_common(1)[0][0]


def _count_deep_nesting_lines(lines):
    """Count lines at nesting depth >= 3 using indentation."""
    indent_unit = _detect_indent_unit(lines)
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        raw_indent = len(line) - len(line.lstrip())
        level = raw_indent // indent_unit if indent_unit > 0 else 0
        if level >= 3:
            count += 1
    return count


def compute_complexity_batch(file_paths, repo_root=None):
    """Compute complexity for multiple files."""
    results = {}
    for fp in file_paths:
        results[fp] = compute_complexity(fp, repo_root)
    return results
