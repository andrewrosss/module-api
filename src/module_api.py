from __future__ import annotations

import argparse
import io
import token
from enum import Enum
from tokenize import generate_tokens
from tokenize import TokenInfo
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


class DefType(Enum):
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
        dest="def_type",
        action="store_const",
        const=DefType.PUBLIC,
        default=DefType.PUBLIC,
        help="Collect only public API definitions (default)",
    )
    defn_group.add_argument(
        "--private",
        dest="def_type",
        action="store_const",
        const=DefType.PRIVATE,
        help="Collect only private API definitions",
    )
    defn_group.add_argument(
        "--all",
        dest="def_type",
        action="store_const",
        const=DefType.ALL,
        help="Collect all API definitions",
    )
    docstring_group = parser.add_mutually_exclusive_group()
    docstring_group.add_argument(
        "--docstrings",
        dest="docstrings",
        action="store_true",
        default=True,
        help="Include docstrings (default)",
    )
    docstring_group.add_argument(
        "--no-docstrings",
        dest="docstrings",
        action="store_false",
        help="Exclude docstrings",
    )

    parser.set_defaults(handler=handler)

    return parser


def handler(ns: argparse.Namespace) -> int:
    files: list[str] = ns.files
    def_type: DefType = ns.def_type
    docstrings: bool = ns.docstrings

    for filename in files:
        entries = [f"# {filename}"]
        with open(filename) as f:
            source_s = f.read()
            api = module_api(source_s, def_type=def_type, include_docstring=docstrings)
            entries.extend(api)
        out_s = "\n\n".join(entries)
        print(out_s)

    return 0


def module_api(
    source_s: str,
    *,
    def_type: DefType = DefType.PUBLIC,
    include_docstring: bool = True,
) -> list[str]:
    def_it = find_definitions(source_s, include_docstring=include_docstring)
    def_lst = [unparse_tokens(d) for d in filter_definitions(def_it, def_type=def_type)]
    return [d.strip() for d in def_lst]


def find_definitions(
    source_s: str,
    *,
    include_docstring: bool = True,
) -> Iterator[list[TokenInfo]]:
    f = io.StringIO(source_s)
    gen = generate_tokens(f.readline)
    for tok in gen:
        if tok.type == token.NAME and tok.string == "def":
            yield _read_function(gen, tok, include_docstring=include_docstring)
        elif tok.type == token.NAME and tok.string == "class":
            yield _read_class(gen, tok, include_docstring=include_docstring)


def _read_function(
    gen: Iterator[TokenInfo],
    tok: TokenInfo,
    *,
    include_docstring: bool = True,
) -> list[TokenInfo]:
    return _read_signature(gen, tok, include_docstring=include_docstring)


def _read_class(
    gen: Iterator[TokenInfo],
    tok: TokenInfo,
    *,
    include_docstring: bool = True,
) -> list[TokenInfo]:
    return _read_signature(gen, tok, include_docstring=include_docstring)


def _read_signature(
    gen: Iterator[TokenInfo],
    tok: TokenInfo,
    *,
    include_docstring: bool = True,
) -> list[TokenInfo]:
    # read until next colon outside parentheses
    signature: list[TokenInfo] = []
    parens = 0
    while tok.exact_type != token.COLON or parens > 0:
        signature.append(tok)
        if tok.exact_type == token.LPAR:
            parens += 1
        elif tok.exact_type == token.RPAR:
            parens -= 1
        tok = next(gen)

    # # add the colon
    # signature.append(tok)

    if include_docstring:
        docstring: list[TokenInfo] = []
        tok = next(gen)
        while tok.exact_type in (token.NEWLINE, token.INDENT, token.STRING):
            docstring.append(tok)
            tok = next(gen)

        # extend if there is a string among the whitespace
        # immediately following the signature
        if any(t.exact_type == token.STRING for t in docstring):
            signature.extend(docstring)

    return signature


def filter_definitions(
    definitions: Iterator[list[TokenInfo]],
    def_type: DefType = DefType.PUBLIC,
) -> Iterator[list[TokenInfo]]:
    for defn in definitions:
        _, name_tok, *_ = defn
        if (
            def_type == DefType.ALL
            or (def_type == DefType.PUBLIC and not name_tok.string.startswith("_"))
            or (def_type == DefType.PRIVATE and name_tok.string.startswith("_"))
        ):
            yield defn


def unparse_tokens(tokens: Sequence[TokenInfo]) -> str:
    _tokens = iter(tokens)
    tok = next(_tokens)
    lines, prev_line = [tok.line], tok.end[0]
    for tok in _tokens:
        if tok.end[0] == prev_line:
            continue
        lines.append(tok.line)
        prev_line = tok.end[0]
    return "".join(lines)


if __name__ == "__main__":
    cli()
