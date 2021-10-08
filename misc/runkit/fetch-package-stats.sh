#!/bin/bash

set -euo pipefail

function fetch_package_versions {
  curl -s -H "Authorization: token $TOKEN" "https://api.github.com/users/EnricoMi/packages/container/publish-unit-test-result-action/versions"
}

function get_package_urls {
  jq -r ".[] | select(.metadata.package_type == \"container\") | select(.metadata.container.tags[] | startswith(\"v\") and contains(\".\")) | .html_url"
}

function extract {
  grep -A 1 "$1" | tail -n 1 | sed -e "s/[^<]*<[^>]*>//" -e "s/<.*//" -e "s/,//"
}

total=0
change=0

urls=$(fetch_package_versions | get_package_urls)
for url in $urls
do
  json=$(curl -s -L "$url")

  pulls=$(extract "Total downloads" <<< "$json")
  month=$(extract "Last 30 days" <<< "$json")

  total=$(( total + pulls ))
  change=$(( change + month ))
  echo "$url: $pulls (+$month)"
done

echo "$total total"
echo "$total" > total
echo "$change in 30 days"
echo "$change" > change
/usr/local/bin/aws s3 cp total s3://github.com-enricomi/publish-unit-test-result.pull.total --acl bucket-owner-full-control --acl public-read
/usr/local/bin/aws s3 cp change s3://github.com-enricomi/publish-unit-test-result.pull.month --acl bucket-owner-full-control --acl public-read
