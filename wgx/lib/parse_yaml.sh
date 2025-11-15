#!/usr/bin/env bash

# Parses a YAML file and returns the value of a given key.

parse_yaml() {
  local file="$1"
  local key="$2"
  yq -r "$key // \"\"" "$file"
}
