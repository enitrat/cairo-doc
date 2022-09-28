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
        self.get_elements_documentation(top_level_elements)
        self.remove_documentation(top_level_elements)
        self.add_documentation(top_level_elements)

        return super().visit_CairoModule(module)

    def get_elements_documentation(self, code_elements: List[CommentedCodeElement]):
        total_elements = len(code_elements)

        # Don't revisit something already visited when inserting lines so visit from end to start
        for i in range(total_elements - 1, -1, -1):
            func = code_elements[i].code_elm
            if skip_element(func):
                continue
            if is_namespace(func):
                namespace_elements = func.code_block.code_elements
                self.get_elements_documentation(namespace_elements)
                continue

            func = code_elements[i].code_elm
            current_function_doc = []
            k = i
            while k > 0 and isinstance(code_elements[k - 1].code_elm, CodeElementEmptyLine):
                comment = code_elements[k-1].comment
                if comment == None:
                    break
                current_function_doc.append(comment)
                k -= 1

            new_documentation = create_function_documentation(
                current_function_doc, func)

            self.documentation[func.name] = new_documentation


    def remove_documentation(self, code_elements: List[CommentedCodeElement]):
        total_elements = len(code_elements)

        # I don't want to revisit something already visited when inserting lines so I visit from bottom to top
        i = -1
        while (True):
            i += 1
            if i == total_elements:
                break

            func = code_elements[i].code_elm

            if skip_element(func):
                continue
            if is_namespace(func):
                namespace_elements = func.code_block.code_elements
                self.remove_documentation(namespace_elements)
                continue;
            # Iterate over all comments on top of the function and remove them
            while isinstance(code_elements[i - 1].code_elm, CodeElementEmptyLine):
                comment = code_elements[i-1].comment
                if comment == None:
                    break
                code_elements.remove(code_elements[i-1])
                total_elements -= 1
                i -= 1

    def add_documentation(self, code_elements: List[CommentedCodeElement]):
        total_elements = len(code_elements)

        for i in range(total_elements - 1, -1, -1):
            func = code_elements[i].code_elm
            if skip_element(func):
                continue
            if is_namespace(func):
                namespace_elements = func.code_block.code_elements
                self.add_documentation(namespace_elements)
                continue;
            
            current_function_doc = self.documentation[func.name]

            for line in reversed(current_function_doc):
                code_elements.insert(i, CommentedCodeElement(
                    comment=line,
                    code_elm=CodeElementEmptyLine()
                ))


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
            current_line = f"@returns {ret.name} "
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


def skip_element(element: CommentedCodeElement):
  # Only generate documentation for functions
    if not isinstance(element, CodeElementFunction):
        return True
    # struct  and storage_var are considered functions but we won't generate documentation for them.
    need_instrumentation = (any(decorator.name not in [
        "storage_var", "event"] for decorator in element.decorators) or len(element.decorators) == 0) and element.element_type not in ['struct']

    return not need_instrumentation


def is_namespace(element: CommentedCodeElement):
    if element.element_type == 'namespace':
        return True

    return False
