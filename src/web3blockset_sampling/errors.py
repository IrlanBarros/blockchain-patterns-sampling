"""Actionable validation failures, also serialized by the CLI."""


class ValidationError(ValueError):
    """A condition that prevents a scientifically valid run."""

