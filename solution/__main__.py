"""python -m solution adapt|eval; Docker-compatible default paths."""

import argparse
import json

from .adapt import adapt
from .eval import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("adapt")
    train.add_argument("--input", default="/input/train.jsonl")
    train.add_argument("--artifacts", default="/artifacts")
    train.add_argument("--language", choices=["original", "es", "en"], default="original")
    train.add_argument("--disable-family", default=None)
    train.add_argument("--no-model", action="store_true")
    train.add_argument("--from-scratch", action="store_true", help="Start with no instantiated rule families")
    test = commands.add_parser("eval")
    test.add_argument("--input", default="/input/test.jsonl")
    test.add_argument("--artifacts", default="/artifacts")
    test.add_argument("--output", default="/output/predictions.csv")
    test.add_argument("--no-model", action="store_true")
    args = parser.parse_args()
    try:
        result = (adapt(args.input, args.artifacts, args.language, args.disable_family, args.no_model,
                        from_scratch=args.from_scratch) if args.command == "adapt"
                  else evaluate(args.input, args.artifacts, args.output, args.no_model))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"{args.command} failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
