#!/bin/sh
set -e
exec uvicorn vibecheck.main:app --host 0.0.0.0 --port "${PORT:-8895}"
