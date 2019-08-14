#!/usr/bin/env python
import argparse, sys

parser = argparse.ArgumentParser(description='Interact session')
parser.add_argument('-c', '--config', dest='config', help='yaml configuration file')
parser.add_argument('-t', '--text', dest='text', default=None, help='query text')

args = parser.parse_args()

if len(sys.argv) < 2:
    parser.print_help()
    parser.exit()

from elsabot.backend import Backend
from nlptools.utils import Config

cfg = Config(args.config)

backend = Backend(args.config, **cfg.backend)

if args.text is not None:
    backend.query(args.text)
else:
    backend.run()


