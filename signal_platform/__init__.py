"""Multi-strategy signal platform helpers.

Keep package import side effects light so research modules can safely import
utility submodules such as ``signal_platform.env`` without dragging the whole
live strategy registry into the import graph.
"""


def get_strategy(*args, **kwargs):
    from .registry import get_strategy as _get_strategy

    return _get_strategy(*args, **kwargs)


def list_strategies(*args, **kwargs):
    from .registry import list_strategies as _list_strategies

    return _list_strategies(*args, **kwargs)


__all__ = ["get_strategy", "list_strategies"]
