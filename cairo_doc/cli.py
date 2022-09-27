import argparse
import sys
import os
from typing import Callable

from starkware.cairo.lang.compiler.ast.module import CairoFile, CairoModule
from starkware.cairo.lang.compiler.parser import parse_file
from starkware.cairo.lang.version import __version__

from rewriter import Rewriter


def cairo_interface_generator(cairo_parser: Callable[[str, str], CairoFile], description: str):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-v", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("files", metavar="file", type=str,
                        nargs="+", help="File names")
    parser.add_argument("-d", "--directory", type=str)
    parser.add_argument("-o", "--output", type=str)

    args = parser.parse_args()
    for path in args.files:
        contract_file = open(path).read()
        dirpath, filename = os.path.split(path)
        contract_name = filename.split(".")[0]
        newfilename = f"{args.output}.cairo" if args.output else "doc_" + filename
        newpath = os.path.join(args.directory or dirpath, newfilename)
        try:

            # Generate the AST of the cairo contract, visit it and generate the interface
            contract = CairoModule(
                cairo_file=cairo_parser(contract_file, filename),
                module_name=path,
            )

            rewriter = Rewriter()
            rewriter.visit(contract)
            new_content = contract.format()

        except Exception as exc:
            print(exc, file=sys.stderr)
            return 1

        print(f"Doc for {newpath}")
        open(newpath, "w").write(new_content)

    return 0


def main():
    def cairo_parser(code, filename): return parse_file(
        code=code, filename=filename)

    return cairo_interface_generator(
        cairo_parser=cairo_parser, description="A tool to automatically generate the interface of a cairo contract."
    )


if __name__ == "__main__":
    sys.exit(main())
