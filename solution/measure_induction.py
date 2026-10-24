"""Reproduce one public induction comparison; scorer alone reads test labels.

python -m solution.measure_induction {library_no_model,from_scratch,hybrid}
Artifacts and metrics are kept separate for each mode. No hyperparameter tuning.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .io import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["library_no_model", "from_scratch", "hybrid"])
    parser.add_argument("--deadline-seconds", type=int, default=3300)
    args = parser.parse_args()
    output, artifacts = Path("out/induce") / args.mode, Path("artifacts") / args.mode
    output.mkdir(parents=True, exist_ok=True)
    if (artifacts / "rules_spec.json").exists():
        parser.error(f"Refusing to overwrite completed run: {artifacts}")
    env = dict(os.environ, ADAPT_MODE="hybrid", INDUCTION_MODEL="openai/gpt-oss-120b",
               EVAL_MODEL="openai/gpt-oss-120b", PYTHONUNBUFFERED="1")
    commands = []
    started = time.monotonic()

    def run(stage, argv):
        command = [sys.executable, "-S", *argv]
        entry = dict(stage=stage, command=command, started_at=datetime.now(timezone.utc).isoformat())
        commands.append(entry)
        write_json(output / "commands.json", commands)
        tick = time.monotonic()
        print(f"[{args.mode}] {stage}", flush=True)
        try:
            with (output / (stage + ".stdout.txt")).open("w") as stdout, (output / (stage + ".stderr.txt")).open("w") as stderr:
                result = subprocess.run(command, env=env, stdout=stdout, stderr=stderr,
                                        timeout=max(1, args.deadline_seconds - (tick - started)))
            entry["returncode"] = result.returncode
        except subprocess.TimeoutExpired:
            entry.update(status="deadline", returncode=124)
        finally:
            entry["wall_seconds"] = time.monotonic() - tick
            write_json(output / "commands.json", commands)
        if entry["returncode"]:
            raise SystemExit(entry["returncode"])

    flags = ["--no-model"] if args.mode == "library_no_model" else []
    run("adapt", ["-m", "solution", "adapt", "--input", "out/public_input/train.jsonl",
                  "--artifacts", str(artifacts), *flags,
                  *(["--from-scratch"] if args.mode == "from_scratch" else [])])
    for split in ("train", "test"):
        predictions = output / (split + ".csv")
        run("eval_" + split, ["-m", "solution", "eval", "--input", f"out/public_input/{split}.jsonl",
                             "--artifacts", str(artifacts), "--output", str(predictions), *flags])
        run("score_" + split, ["src/evaluate.py", "--test", f"data/public_{split}.csv",
                              "--predictions", str(predictions), "--out", str(output / (split + "_score.json"))])
    logs = {"adapt": json.loads((artifacts / "model_log.json").read_text())["stats"]}
    logs.update({split: json.loads((output / (split + ".log.json")).read_text())["stats"] for split in ("train", "test")})
    write_json(output / "usage.json", dict(by_stage=logs, wall_seconds=time.monotonic()-started))
    print(f"[{args.mode}] completed", flush=True)


if __name__ == "__main__":
    main()
