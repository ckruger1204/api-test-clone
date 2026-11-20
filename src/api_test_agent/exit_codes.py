# src/api_test_agent/exit_codes.py
from enum import IntEnum
class ExitCode(IntEnum):
    OK = 0
    INTERNAL = 1
    USAGE = 2
    SPEC_NOT_FOUND = 3
    SPEC_INVALID = 4
    GENERATION_ERROR = 5
    TEST_FAILURES = 6