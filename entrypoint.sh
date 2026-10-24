#!/bin/sh
set -eu

case "${1:-}" in
  adapt)
    shift
    exec python -m solution adapt \
      --input /input/train.jsonl \
      --artifacts /artifacts \
      "$@"
    ;;
  eval)
    shift
    exec python -m solution eval \
      --input /input/test.jsonl \
      --artifacts /artifacts \
      --output /output/predictions.csv \
      "$@"
    ;;
  *)
    echo "usage: docker run ... IMAGE {adapt|eval}" >&2
    exit 64
    ;;
esac
