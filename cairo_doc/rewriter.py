from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from starkware.cairo.lang.compiler.ast.code_elements import CodeElementFunction, CodeBlock, CodeElementEmptyLine, CommentedCodeElement
from starkware.cairo.lang.compiler.ast.visitor import Visitor
from starkware.cairo.lang.compiler.ast.module import CairoFile, CairoModule
from starkware.cairo.lang.compiler.ast.types import TypedIdentifier
from starknet_interface_generator.utils import to_camel_case

valid_tags = ['@notice', '@param', '@returns', '@inheritdoc']


class Rewriter(Visitor):
    """
    Generates an interface from a Cairo contract.
    """

    def __init__(self):
        super().__init__()
        self.documentation = {}

    def _visit_default(self, obj):
        # top-level code is not generated
        return obj

    def visit_CodeElementFunction(self, elm: CodeElementFunction):
        return super().visit_CodeElementFunction(elm)

    def visit_CodeBlock(self, elm: CodeBlock):
        # self.parse_block(elm)
        return super().visit_CodeBlock(elm)

    def visit_CairoModule(self, module: CairoModule):
        top_level_elements = module.cairo_file.code_block.code_elements
        self.get_documentation(top_level_elements)
        self.remove_documentation(top_level_elements)
        self.add_documentation(top_level_elements)

        return super().visit_CairoModule(module)

    def get_documentation(self, top_level_elements):
        total_elements = len(top_level_elements)

        # I don't want to revisit something already visited when inserting lines so I visit from bottom to top
        for i in range(total_elements - 1, -1, -1):

            func = top_level_elements[i].code_elm

            # Only generate documentation for functions
            if not isinstance(func, CodeElementFunction):
                continue
            # struct, namespaces and storage_var are considered functions but we won't generate documentation for them.
            need_instrumentation = any(decorator.name not in [
                "storage_var"] for decorator in func.decorators) and func.element_type not in ['struct', 'namespace']
            if not need_instrumentation:
                continue

            # Store current function documentation in an array.
            current_function_doc = []
            k = i
            while k > 0 and isinstance(top_level_elements[k - 1].code_elm, CodeElementEmptyLine):
                comment = top_level_elements[k-1].comment
                if comment == None:
                    break
                current_function_doc.append(comment)
                k -= 1

            # inverse because we want to write the last documentation line first
            new_documentation = create_function_documentation(
                current_function_doc, func)

            self.documentation[func.name] = new_documentation

    def remove_documentation(self, top_level_elements):
        total_elements = len(top_level_elements)

        # I don't want to revisit something already visited when inserting lines so I visit from bottom to top
        i = -1
        while (True):
            i += 1
            if i == total_elements:
                break

            func = top_level_elements[i].code_elm

            # Only generate documentation for functions
            if not isinstance(func, CodeElementFunction):
                continue
            # struct, namespaces and storage_var are considered functions but we won't generate documentation for them.
            need_instrumentation = any(decorator.name not in [
                "storage_var"] for decorator in func.decorators) and func.element_type not in ['struct', 'namespace']
            if not need_instrumentation:
                continue

            # Store current function documentation in an array.
            while isinstance(top_level_elements[i - 1].code_elm, CodeElementEmptyLine):
                comment = top_level_elements[i-1].comment
                if comment == None:
                    break
                top_level_elements.remove(top_level_elements[i-1])
                total_elements -= 1
                i -= 1

    def add_documentation(self, top_level_elements):
        total_elements = len(top_level_elements)

        # I don't want to revisit something already visited when inserting lines so I visit from bottom to top
        for i in range(total_elements - 1, -1, -1):

            func = top_level_elements[i].code_elm

            # Only generate documentation for functions
            if not isinstance(func, CodeElementFunction):
                continue
            # struct, namespaces and storage_var are considered functions but we won't generate documentation for them.
            need_instrumentation = any(decorator.name not in [
                "storage_var"] for decorator in func.decorators) and func.element_type not in ['struct', 'namespace']
            if not need_instrumentation:
                continue

            current_function_doc = self.documentation[func.name]

            for j, line in enumerate(reversed(current_function_doc)):
                # Return true if any string in documentation contains the substring line.
                # TODO add an offset in case the documentation has been partially generated before
                # e.g. if there is a @dev tag but no notice tag
                # -> we want notice - dev - param - return

                # TODO : Insert if the line doesn't exist, replace otherwise.

                top_level_elements.insert(i, CommentedCodeElement(
                    comment=line,
                    code_elm=CodeElementEmptyLine()
                ))


def verify_documentation_tag(element_index: int, tag: str):
    pass


def create_function_documentation(current_function_doc: List[str], func: CodeElementFunction) -> List[str]:

    tag_notice = ['@notice']
    tag_dev = []
    tag_inheritdoc = []
    tag_params = []
    tag_returns = []

    # notice
    existing_notice = first_substring(current_function_doc, '@notice ')
    if existing_notice:
        tag_notice[0] = existing_notice

    # func arguments
    for i, arg in enumerate(func.arguments.identifiers):
        current_line = f"@param {arg.name} "
        existing_line = first_substring(current_function_doc, current_line)
        if existing_line:
            tag_params.append(existing_line)
        else:
            tag_params.append(current_line)

    # func return values
    if func.returns != None:
        for ret in func.returns.members:
            # TODO : two types of returns, named and not named
            current_line = f"@returns {ret.name} : {ret.typ.format()} "
            existing_line = first_substring(current_function_doc, current_line)
            if existing_line:
                tag_returns.append(existing_line)
            else:
                tag_returns.append(current_line)

    existing_dev = first_substring(current_function_doc, '@dev')
    if existing_dev:
        tag_notice.append(existing_dev)

    existing_inheritdoc = first_substring(current_function_doc, '@inheritdoc')
    documentation = tag_notice + tag_dev + tag_params + tag_returns

    # If the documentation has been generated with inheritdoc, leave it as is.
    if existing_inheritdoc:
        documentation = [existing_inheritdoc]

    return documentation


def first_substring(strings, substring):
    for i, s in enumerate(strings):
        if substring in s:
            return s
    return None
