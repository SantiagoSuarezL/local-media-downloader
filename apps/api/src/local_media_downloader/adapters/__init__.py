"""Adapters: the only packages allowed to know external tools.

Each external dependency sits behind a port declared in ``domain``
(ENGINEERING_PRINCIPLES #24), so any of them can be replaced without touching
the domain layer.
"""
