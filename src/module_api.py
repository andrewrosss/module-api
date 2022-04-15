from __future__ import annotations

import argparse
import io
import token
import tokenize
from enum import Enum
from typing import Iterator
from typing import NoReturn
from typing import Sequence


__version__ = "0.1.0"


def cli() -> NoReturn:
    raise SystemExit(main())


def main(args: Sequence[str] | None = None) -> int | str:
    parser = create_parser()
    ns = parser.parse_args(args)
    debug: bool = ns.debug

    try:
        return ns.handler(ns)
    except Exception as e:
        if debug:
            raise
        else:
            return str(e)


class _Def(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ALL = "all"


def create_parser(
    parser: argparse.ArgumentParser | None = None,
) -> argparse.ArgumentParser:
    parser = parser or argparse.ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=__version__)
    parser.add_argument(
        "-D",
        "--debug",
        action="store_true",
        default=False,
        help="run program in debug mode",
    )
    parser.add_argument(
        "files",
        metavar="file",
        nargs="+",
        help="Files from which to extract the API definitions",
    )
    defn_group = parser.add_mutually_exclusive_group()
    defn_group.add_argument(
        "--public",
        dest="definitions",
        action="store_const",
        const=_Def.PUBLIC,
        default=_Def.PUBLIC,
        help="Collect only public API definitions (default)",
    )
    defn_group.add_argument(
        "--private",
        dest="definitions",
        action="store_const",
        const=_Def.PRIVATE,
        help="Collect only private API definitions",
    )
    defn_group.add_argument(
        "--all",
        dest="definitions",
        action="store_const",
        const=_Def.ALL,
        help="Collect all API definitions",
    )

    parser.set_defaults(handler=handler)

    return parser


def handler(ns: argparse.Namespace) -> int:
    files: list[str] = ns.files
    definitions: _Def = ns.definitions

    for filename in files:
        print(f"# {filename}\n")
        with open(filename) as f:
            source_s = f.read()
            for defn in find_definitions(source_s):
                if (
                    definitions == _Def.ALL
                    or (
                        definitions == _Def.PUBLIC
                        and not defn.strip().startswith("def _")
                    )
                    or (
                        definitions == _Def.PRIVATE and defn.strip().startswith("def _")
                    )
                ):
                    print(defn)

    return 0


def find_definitions(source_s: str) -> Iterator[str]:
    f = io.StringIO(source_s)
    gen = tokenize.generate_tokens(f.readline)
    for tok in gen:
        if tok.type == token.NAME and tok.string == "def":
            yield _read_function(gen, tok)
        elif tok.type == token.NAME and tok.string == "class":
            yield _read_class(gen, tok)


def _read_function(gen: Iterator[tokenize.TokenInfo], tok: tokenize.TokenInfo):
    # function definition, read until next colon outside
    # parentheses.
    definition, prev_line = [tok.line], tok.end[0]
    parens = 0
    while tok.exact_type != token.COLON or parens > 0:
        if prev_line != tok.end[0]:
            definition.append(tok.line)
            prev_line = tok.end[0]
        if tok.exact_type == token.LPAR:
            parens += 1
        elif tok.exact_type == token.RPAR:
            parens -= 1
        tok = next(gen)
    # grab line containing colon
    if prev_line != tok.end[0]:
        definition.append(tok.line)
        prev_line = tok.end[0]
    # function docstring, read newlines and indents until
    # next
    tok = next(gen)
    while tok.exact_type in (token.NEWLINE, token.INDENT, token.STRING):
        if prev_line != tok.end[0] and tok.exact_type == token.STRING:
            definition.append(tok.line)
            prev_line = tok.end[0]
        tok = next(gen)
    return "".join(definition)


def _read_class(gen: Iterator[tokenize.TokenInfo], tok: tokenize.TokenInfo):
    return _read_function(gen, tok)


if __name__ == "__main__":
    cli()
