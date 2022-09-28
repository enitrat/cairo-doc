from typing import Dict, List
from starkware.cairo.lang.compiler.ast.code_elements import CodeElementFunction, CodeBlock, CodeElementEmptyLine, CommentedCodeElement
from starkware.cairo.lang.compiler.ast.visitor import Visitor
from starkware.cairo.lang.compiler.ast.module import CairoModule
from starkware.cairo.lang.compiler.ast.cairo_types import TypeTuple


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

    def visit_CairoModule(self, module: CairoModule):
        """Visit a CairoModule and fill the functions documentation."""
        top_level_elements = module.cairo_file.code_block.code_elements
        self.get_elements_documentation(top_level_elements)
        self.remove_documentation(top_level_elements)
        self.add_documentation(top_level_elements)

        return super().visit_CairoModule(module)

    def get_elements_documentation(self, code_elements: List[CommentedCodeElement]):
        """Gets the current documentation of the functions in the file.
        The documentation is stored in a dictionary with the function name as key and the documentation as value.
        """
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

            current_function_doc = []
            k = i
            while isinstance(code_elements[k - 1].code_elm, CodeElementEmptyLine):
                comment = code_elements[k-1].comment
                if comment == None:
                    break
                current_function_doc.append(comment)
                k -= 1

            new_documentation = create_function_documentation(
                current_function_doc, func)

            self.documentation[func.name] = new_documentation

    def remove_documentation(self, code_elements: List[CommentedCodeElement]):
        """Removes the old documentation from the code elements."""
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
                continue
            # Iterate over all comments on top of the function and remove them
            while isinstance(code_elements[i - 1].code_elm, CodeElementEmptyLine):
                comment = code_elements[i-1].comment
                if comment == None:
                    break
                code_elements.remove(code_elements[i-1])
                total_elements -= 1
                i -= 1

    def add_documentation(self, code_elements: List[CommentedCodeElement]):
        """Adds the new documentation to the code elements."""
        total_elements = len(code_elements)

        for i in range(total_elements - 1, -1, -1):
            func = code_elements[i].code_elm
            if skip_element(func):
                continue
            if is_namespace(func):
                namespace_elements = func.code_block.code_elements
                self.add_documentation(namespace_elements)
                continue

            current_function_doc = self.documentation[func.name]

            for line in reversed(current_function_doc):
                code_elements.insert(i, CommentedCodeElement(
                    comment=line,
                    code_elm=CodeElementEmptyLine()
                ))


def create_function_documentation(current_function_doc: List[str], func: CodeElementFunction) -> List[str]:
    """Returns the documentation for a function as a list of string (1 string per line)
    Already existing documentation is kept
    New documentation is added if it doesn't exist
    """
    tag_notice = ['@notice']
    tag_dev = []
    tag_inheritdoc = []
    tag_params = []
    tag_returns = []

    # notice
    existing_notice = first_substring(current_function_doc, '@notice ')
    if existing_notice:
        tag_notice[0] = existing_notice

    # dev
    existing_dev = first_substring(current_function_doc, '@dev')
    if existing_dev:
        tag_notice.append(existing_dev)

    # func parameters
    for i, arg in enumerate(func.arguments.identifiers):
        current_line = f"@param {arg.name} "
        tag_params.append(add_documentation_item(
            current_function_doc, current_line))

    # func return values
    if func.returns != None:
        # handle typed and tuple returns
        if not isinstance(func.returns, TypeTuple):
            current_line = f"@returns {func.returns.format()}"
            tag_returns.append(add_documentation_item(
                current_function_doc, current_line))

        else:
            for ret in func.returns.members:
                current_line = f"@returns {ret.name} "
                tag_returns.append(add_documentation_item(
                    current_function_doc, current_line))

    existing_inheritdoc = first_substring(current_function_doc, '@inheritdoc')
    documentation = tag_notice + tag_dev + tag_params + tag_returns

    # If the documentation has been generated with inheritdoc, leave it as is.
    if existing_inheritdoc:
        documentation = [existing_inheritdoc]

    return documentation


def first_substring(strings: List[str], substring: str):
    """Returns the index of the first occurrence of a substring in a list of strings"""
    for s in strings:
        if substring in s:
            return s
    return None


def skip_element(element: CommentedCodeElement):
    """
    Skip elements that are not functions or namespaces
    """
    if not isinstance(element, CodeElementFunction):
        return True
    # struct  and storage_var are considered functions but we won't generate documentation for them.
    need_instrumentation = (any(decorator.name not in [
        "storage_var", "event"] for decorator in element.decorators) or len(element.decorators) == 0) and element.element_type not in ['struct']

    return not need_instrumentation


def is_namespace(element: CommentedCodeElement):
    """Returns if the element is a namespace"""
    if element.element_type == 'namespace':
        return True

    return False


def add_documentation_item(current_function_doc, item: str):
    """Returns the correct item to add to the documentation
    If the element already existed, return it instead of the default one
    """
    existing_line = first_substring(current_function_doc, item)
    return existing_line or item
