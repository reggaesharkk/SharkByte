"""Reproduce 50,000 deterministic H4 arithmetic comparisons as JSONL or a digest."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

from . import h4_bits as producer, h4_replay as replay

SEED = "sharkbyte-h4-hostile-v1"
COUNT = 50_000
EDGE = (0, 1, (1 << 52)-1, 1 << 52, (1 << 52)+1,
        0x3ff0000000000000, 0x7feffffffffffffe, 0x7fefffffffffffff)


def inputs(index):
    raw = hashlib.sha256(f"{SEED}:{index}".encode("ascii")).digest()
    words = [int.from_bytes(raw[i:i+8], "big") for i in range(0, 32, 8)]
    finite = [word ^ (1 << 52) if (word >> 52) & 2047 == 2047 else word
              for word in words]
    family = index % 5
    if family == 1:
        finite = [EDGE[w % len(EDGE)] | (w & producer.SIGN) for w in words]
    elif family == 2:
        finite[2:] = [w ^ producer.SIGN for w in finite[:2]]
        finite[index % 2] ^= 1
    elif family == 3:
        # A max finite operand plus around half an ulp exercises overflow ties.
        finite = [producer.MAX_FINITE, producer.MAX_FINITE | producer.SIGN,
                  0x7c90000000000000 + (index % 3) - 1,
                  0x7c90000000000000 + (index % 3) - 1]
    elif family == 4:
        finite = [(w & ((1 << 53)-1)) | (w & producer.SIGN) for w in words]
    return [tuple(finite[:2]), tuple(finite[2:])]


def evaluate(engine, state):
    try:
        return engine.step(state, "h", [0])
    except ValueError as exc:
        if "overflow" not in str(exc):
            raise
        return "OVERFLOW"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=Path, help="write all exact inputs and outputs as JSONL")
    args = parser.parse_args()
    stream = args.words.open("x", encoding="utf-8", newline="\n") if args.words else None
    checksum = hashlib.sha256()
    overflow = 0
    start = perf_counter()
    try:
        for index in range(COUNT):
            state = inputs(index)
            actual = evaluate(producer, state)
            expected = evaluate(replay, state)
            if actual != expected:
                raise SystemExit(json.dumps({"decision": "FAIL", "index": index,
                                            "input": state, "actual": actual, "expected": expected}))
            overflow += actual == "OVERFLOW"
            row = json.dumps([index, state, actual], separators=(",", ":"))+"\n"
            checksum.update(row.encode("ascii"))
            if stream:
                stream.write(row)
    finally:
        if stream:
            stream.close()
    files = [Path(__file__), Path(producer.__file__), Path(replay.__file__)]
    print(json.dumps({"decision": "PASS", "seed": SEED, "cases": COUNT,
                      "overflow_cases": overflow, "words_sha256": checksum.hexdigest(),
                      "seconds": perf_counter()-start, "source_sha256": {
                          p.name: hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest()
                          for p in files}}, sort_keys=True))


if __name__ == "__main__":
    main()
