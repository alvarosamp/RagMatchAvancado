#!/usr/bin/env python3
"""Executa coleta e estruturação sem IA em uma chamada."""
import argparse
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__, add_help=False)
parser.add_argument('--output', required=True)
args, rest = parser.parse_known_args()
root = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(root / 'coletar.py'), '--output', args.output, *rest], check=True)
subprocess.run([sys.executable, str(root / 'estruturar.py'), '--output', args.output], check=True)
