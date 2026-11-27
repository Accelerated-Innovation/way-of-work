#!/usr/bin/env python3
"""Run the Way of Work validators without installing anything: `python wow.py <command>`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wow_validators.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
