#!/bin/bash

set -euo pipefail

function fetch_package_versions {
  curl -s -H "Authorization: token $TOKEN" "https://api.github.com/users/EnricoMi/packages/container/publish-unit-test-result-action/versions"
}

function get_package_urls {
  jq -r ".[] | select(.metadata.package_type == \"container\") | select(.metadata.container.tags[] | startswith(\"v\") and contains(\".\")) | .html_url"
}

function extract_pulls {
  grep -A 1 "Last 30 days" | tail -n 1 | sed -e "s/[^<]*<[^>]*>//" -e "s/<.*//" -e "s/,//"
}

sum=0
urls=$(fetch_package_versions | get_package_urls)
for url in $urls
do
  pulls=$(curl -s "$url" | extract_pulls)
  sum=$(( sum + pulls ))
  echo $url: $pulls
done

echo "$sum in 30 days"
echo "$sum" > counts
/usr/local/bin/aws s3 cp counts s3://github.com-enricomi/publish-unit-test-result.pull.count --acl bucket-owner-full-control --acl public-read
