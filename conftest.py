"""Ensures the project root is importable as `src...` when running pytest,
regardless of the directory pytest is invoked from. Intentionally empty
otherwise -- pytest adds this file's directory to sys.path automatically.
"""
