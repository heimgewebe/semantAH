#!/usr/bin/env bash

# Provides basic logging functions.

log_info() {
  echo "[INFO] $*"
}

log_error() {
  echo "[ERROR] $*" >&2
}
