from pathlib import Path
from typing import Any, List, Type, TypeVar

T = TypeVar("T")


def find_elements_of_type(elements: List[Any], element_type: Type[T]) -> List[T]:
    return [elem for elem in elements if isinstance(elem, element_type)]


def assert_element_of_type(elements: List[Any], element_type: Type[T]) -> T:
    elements = find_elements_of_type(elements, element_type)
    assert elements, f"No element of type {element_type.__name__} found"
    assert len(elements) == 1, f"More than one element of type {element_type.__name__} found"
    return elements[0]


def assert_elements_of_type(elements: List[Any], element_type: Type[T], count: int) -> List[T]:
    elements = find_elements_of_type(elements, element_type)
    assert len(elements) == count, f"Expected {count} elements of type {element_type.__name__}, found {len(elements)}"
    return elements


def write_file(file: Path, content: str) -> Path:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content)
    return file
