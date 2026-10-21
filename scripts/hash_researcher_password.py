"""Generate a SeasonLens researcher password hash without printing the password."""
from getpass import getpass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/backend-core/src"),
                str(ROOT / "extensions/seasonlens/backend/src")]

from seasonlens import password_hash  # noqa: E402


def main() -> None:
    first = getpass("Researcher password: ")
    second = getpass("Confirm password: ")
    if len(first) < 12:
        raise SystemExit("Use a password with at least 12 characters.")
    if first != second:
        raise SystemExit("Passwords did not match.")
    print(password_hash(first))


if __name__ == "__main__":
    main()
