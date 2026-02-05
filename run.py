#! /usr/bin/env python3
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--expl", action="store_true")

args = parser.parse_args()

if args.expl:
    import src.exploration
