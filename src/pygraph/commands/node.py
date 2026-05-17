from __future__ import annotations

from pygraph.query import GraphQuery


def _fmt(val: object) -> str:
    if val is None:
        return ""
    s = str(val)
    return s.strip()


def run(query: GraphQuery, name: str) -> None:
    symbol = query.get_symbol(name)
    if not symbol:
        print(f"Symbol '{name}' not found")
        return

    print(f"Name:       {symbol.name}")
    print(f"Kind:       {symbol.kind}")
    print(f"File:       {symbol.file}")
    print(f"Lines:      {symbol.line}-{symbol.end_line}")
    print(f"Exported:   {symbol.is_exported}")
    if symbol.receiver:
        print(f"Receiver:   {symbol.receiver}")
    if symbol.doc:
        print(f"Doc:        {_fmt(symbol.doc)}")
    if symbol.signature:
        print(f"Signature:  {_fmt(symbol.signature)}")
    if symbol.type_annotation:
        print(f"Returns:    {symbol.type_annotation}")
    if symbol.arity is not None:
        print(f"Arity:      {symbol.arity}")
    if symbol.decorators:
        print(f"Decorators: {', '.join(symbol.decorators)}")
    if symbol.bases:
        print(f"Bases:      {', '.join(symbol.bases)}")
    if symbol.struct_fields:
        for f in symbol.struct_fields:
            print(f"  Field: {f.name}: {f.type}")
    if symbol.is_async:
        print("Async:      yes")
    if symbol.is_generator:
        print("Generator:  yes")
    if symbol.is_classmethod:
        print("Classmethod: yes")
    if symbol.is_staticmethod:
        print("Staticmethod: yes")
    if symbol.is_property:
        print("Property:   yes")
