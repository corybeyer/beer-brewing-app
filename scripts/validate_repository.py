"""Check source organization and boundaries without changing repository files."""
import argparse
import json
from pathlib import Path
import sys

from validation.repository import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Emit a machine-readable result')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        result = validate(root)
    except (ValueError, OSError) as error:
        print(f'Validation could not run: {error}', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for item in result['findings']:
            print(f"{item['path']}:{item['line']} [{item['rule']}] {item['message']}")
        print(f"{'PASS' if result['passed'] else 'FAIL'}: {result['files_checked']} source files; {len(result['findings'])} policy findings.")
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
