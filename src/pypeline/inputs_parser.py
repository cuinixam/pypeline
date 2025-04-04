import argparse
import distutils.util
from typing import Any, Dict, List

from py_app_dev.core.exceptions import UserNotificationException

from .domain.config import InputType, ProjectInput


def _map_type_for_argparse(input_type: InputType) -> Any:
    if input_type == "string":
        return str
    elif input_type == "integer":
        return int
    elif input_type == "boolean":
        return lambda x: bool(distutils.util.strtobool(x))
    else:
        raise ValueError(f"Unsupported input type specified: {input_type}")


def create_argument_parser_from_definitions(
    input_definitions: Dict[str, ProjectInput],
    description: str = "Pypeline inputs parser.",
) -> argparse.ArgumentParser:
    """Creates and configures an ArgumentParser based on input definitions."""
    parser = argparse.ArgumentParser(
        description=description,
        exit_on_error=False,
    )

    for name, definition in input_definitions.items():
        arg_type = _map_type_for_argparse(definition.type)

        help_text = definition.description or f"Input parameter '{name}'."
        help_text += f" (Type: {definition.type}"
        if definition.default is not None:
            help_text += f", Default: {definition.default}"
        help_text += ")"

        parser.add_argument(
            f"--{name}",
            dest=name,  # Attribute name in the parsed namespace
            help=help_text,
            type=arg_type,  # Type conversion function
            required=definition.required,
            default=definition.default,
        )

    return parser


class InputsParser:
    """Parses input arguments based on definitions using argparse."""

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        self.parser = parser

    @classmethod
    def from_inputs_definitions(
        cls,
        input_definitions: Dict[str, ProjectInput],
        description: str = "Pypeline inputs parser.",
    ) -> "InputsParser":
        """Factory method to create an InputsParser instance from input definitions."""
        return cls(create_argument_parser_from_definitions(input_definitions, description))

    def parse_inputs(self, inputs: List[str]) -> Dict[str, Any]:
        """Parses and validates the provided input strings against the configured parser. Inputs are expected as a list of 'name=value' elements."""
        try:
            args = []
            for item in inputs:
                if "=" not in item:
                    raise UserNotificationException(f"Invalid input format: '{item}', expected 'name=value'")
                name, value = item.split("=", 1)
                args.append(f"--{name}")
                args.append(value)

            parsed_namespace = self.parser.parse_args(args)
            return vars(parsed_namespace)
        except argparse.ArgumentError as e:
            error_message = f"Input validation error: {e}"
            raise UserNotificationException(error_message) from e
        except SystemExit as e:
            error_message = f"Input parsing failed: {e}"
            raise UserNotificationException(error_message) from e
        except Exception as e:
            error_message = f"An unexpected error occurred during input parsing: {e}"
            raise UserNotificationException(error_message) from e
