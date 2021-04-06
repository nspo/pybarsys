#!/bin/bash

# https://unix.stackexchange.com/a/137639/169109

function fail {
  echo $1 >&2
  exit 1
}

function retry {
  local n=1
  local max=13
  local delay=5
  while true; do
    "$@" && break || {
      if [[ $n -lt $max ]]; then
        ((n++))
        echo "Command failed. Attempt $n/$max:"
        sleep $delay;
      else
        fail "The command has failed after $n attempts."
      fi
    }
  done
}

retry "$@"
