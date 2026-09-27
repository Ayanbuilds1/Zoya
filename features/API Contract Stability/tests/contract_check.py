from __future__ import annotations

import ast
import sys
from pathlib import Path


PROJECT_ROOT = Path(sys.argv[1]).resolve()


def load_tree(relative: str) -> tuple[Path, ast.Module]:
    path = PROJECT_ROOT / relative
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        fail(f"SyntaxError in {relative}: {exc}")
    except OSError as exc:
        fail(f"Cannot read {relative}: {exc}")
    return path, tree


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"[PASS] {message}")


def class_node(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    fail(f"Missing class {name}")


def method_node(cls: ast.ClassDef, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    fail(f"Missing method {cls.name}.{name}")


def parameter_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = fn.args
    positional = [a.arg for a in (*args.posonlyargs, *args.args)]
    if args.vararg:
        positional.append(f"*{args.vararg.arg}")
    positional.extend(a.arg for a in args.kwonlyargs)
    if args.kwarg:
        positional.append(f"**{args.kwarg.arg}")
    return positional


def call_names(node: ast.AST, target: str) -> list[set[str]]:
    calls: list[set[str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func_name = None
            if isinstance(child.func, ast.Attribute):
                func_name = child.func.attr
            elif isinstance(child.func, ast.Name):
                func_name = child.func.id
            if func_name == target:
                calls.append({kw.arg for kw in child.keywords if kw.arg})
    return calls


def main() -> int:
    chat_path, chat_tree = load_tree("app/core/chat.py")
    manager_path, manager_tree = load_tree("app/memory/manager.py")
    routes_path, routes_tree = load_tree("app/api/routes/chat.py")
    ok("chat.py parses")
    ok("manager.py parses")
    ok("chat route parses")

    chat_cls = class_node(chat_tree, "ZoyaChatService")
    manager_cls = class_node(manager_tree, "MemoryManager")

    list_chat = method_node(chat_cls, "list_conversations")
    create_chat = method_node(chat_cls, "create_conversation")
    list_mem = method_node(manager_cls, "list_conversations")
    relevant_mem = method_node(manager_cls, "get_relevant_memories")

    ok("ZoyaChatService.list_conversations exists")
    ok("ZoyaChatService.create_conversation exists")
    ok("MemoryManager.list_conversations exists")
    ok("MemoryManager.get_relevant_memories exists")

    required_chat_list = {"self", "user_id", "limit"}
    if not required_chat_list.issubset(parameter_names(list_chat)):
        fail(f"ZoyaChatService.list_conversations parameters are {parameter_names(list_chat)}")

    if not {"self", "user_id"}.issubset(parameter_names(create_chat)):
        fail(f"ZoyaChatService.create_conversation parameters are {parameter_names(create_chat)}")

    if not {"self", "user_id", "limit"}.issubset(parameter_names(list_mem)):
        fail(f"MemoryManager.list_conversations parameters are {parameter_names(list_mem)}")

    memory_params = set(parameter_names(relevant_mem))
    if not {"self", "user_id", "query", "limit"}.issubset(memory_params):
        fail(f"MemoryManager.get_relevant_memories parameters are {parameter_names(relevant_mem)}")

    ok("conversation/memory method signatures are compatible")

    # Check for stale conversation API assumptions in the chat service.
    chat_calls_list = call_names(chat_cls, "list_conversations")
    for kwargs in chat_calls_list:
        unknown = kwargs - {"user_id", "limit"}
        if unknown:
            fail(f"chat.py calls list_conversations with unsupported kwargs: {sorted(unknown)}")

    # Check every get_relevant_memories call in chat.py against manager signature.
    supported_memory_kwargs = memory_params - {"self"}
    for kwargs in call_names(chat_cls, "get_relevant_memories"):
        unknown = kwargs - supported_memory_kwargs
        if unknown:
            fail(f"chat.py calls get_relevant_memories with unsupported kwargs: {sorted(unknown)}")

    ok("chat.py memory calls match MemoryManager signature")

    # API route surface: look for the expected conversation endpoints.
    source = routes_path.read_text(encoding="utf-8")
    required_fragments = (
        "/conversations",
        "list_conversations",
        "create_conversation",
    )
    for fragment in required_fragments:
        if fragment not in source:
            fail(f"chat API route is missing expected contract fragment: {fragment}")
    ok("conversation API route surface exists")

    # Compile-only check of the touched Python surface using the selected interpreter.
    import py_compile

    for rel in ("app/core/chat.py", "app/memory/manager.py", "app/api/routes/chat.py"):
        try:
            py_compile.compile(str(PROJECT_ROOT / rel), doraise=True)
        except py_compile.PyCompileError as exc:
            fail(f"py_compile failed for {rel}: {exc}")
    ok("Python compile checks passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
