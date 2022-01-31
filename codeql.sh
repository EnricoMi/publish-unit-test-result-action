/codeql database trace-command /codeql_databases/python -- /codeql/python/tools/autobuild.sh
/codeql database finalize --finalize-dataset --threads=2 /codeql_databases/python --ram=5927
/codeql database run-queries --ram=5927 --threads=2 /codeql_databases/python --min-disk-free=1024 -v /codeql_databases/python-queries-builtin.qls
/codeql database interpret-results --threads=2 --format=sarif-latest -v --output=/python.sarif --no-sarif-add-snippets --print-diagnostics-summary --print-metrics-summary --sarif-group-rules-by-pack --sarif-add-query-help /codeql_databases/python /codeql_databases/python-queries-builtin.qls
/codeql database print-baseline /codeql_databases/python
/codeql database cleanup /codeql_databases/python --mode=brutal
