#!/bin/bash

set -euo pipefail

case "$RUNNER_OS" in
  Linux*)
    action="linux"
    ;;
  macOS*)
    action="macos"
    ;;
  Windows*)
    action="windows/bash"
    ;;
  *)
    echo "::error::Unsupported operating system: $RUNNER_OS"
    exit 1
    ;;
esac

in_runs=false
in_check=false
in_run=false
in_cleanup=false

while IFS= read -r line
do
  if [ "$line" == "runs:" ]; then in_runs=true
  elif [ $in_runs == true ] && [[ "$line" == *"- name: Check OS" ]]; then in_check=true
  elif [ $in_runs == true ] && [[ "$line" == *"- name: Run" ]]; then in_check=false; in_run=true
  elif [ $in_runs == true ] && [[ "$line" == *"- name: Clean up" ]]; then in_run=false; in_cleanup=true
  elif [ "$line" == "branding:" ]; then in_cleanup=false
  fi

  if [ $in_run == true ] && [[ "$line" == *" uses: "* ]]; then
    # use $action in uses: ...
    echo "${line/%:*/: ./enricomi-publish-action-proxy/$action}"
  elif [ $in_check != true ] && [ $in_cleanup != true ] && ( [ $in_run != true ] || [[ "$line" != *" if:"* ]] ); then
    echo "$line"
  fi
done < "$GITHUB_ACTION_PATH/action.yml"
