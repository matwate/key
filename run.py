#! /usr/bin/env python3
import argparse
import sys
from subprocess import run

parser = argparse.ArgumentParser()
parser.add_argument("--expl", action="store_true")

args = parser.parse_args()

if args.expl:

    res = run(["python", "src/exploration.py"], capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
