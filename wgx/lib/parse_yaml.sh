#!/usr/bin/env bash

# Parses a YAML file and returns the value of a given key.

parse_yaml() {
  local file="$1"
  local key="$2"
  if ! command -v yq >/dev/null 2>&1; then
    echo "yq not found; please install it to use wgx locally" >&2
    return 1
  fi
  yq -r "$key // \"\"" "$file"
}
