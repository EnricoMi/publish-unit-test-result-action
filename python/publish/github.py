import logging

from urllib3 import Retry
from urllib3.exceptions import MaxRetryError, ResponseError


class GitHubRetry(Retry):
    def __init__(self,
                 total,
                 backoff_factor,
                 allowed_methods,
                 status_forcelist):
        # 403 is too broad to be retried, but GitHub API signals rate limits via 403
        # we retry 403 and look into the response header via Retry.increment
        super().__init__(total=total,
                         backoff_factor=backoff_factor,
                         allowed_methods=allowed_methods,
                         status_forcelist=status_forcelist + [403])

    def increment(self,
                  method=None,
                  url=None,
                  response=None,
                  error=None,
                  _pool=None,
                  _stacktrace=None):
        if response:
            logging.info(f'Request {method} {url} failed: {response.reason}')
            logging.debug(f'Response headers:')
            for field, value in response.headers.items():
                logging.debug(f'- {field}: {value}')

            # we retry 403 only if there is a Retry-After header (indicating it is retry-able)
            if response.status == 403:
                if 'Retry-After' in response.headers:
                    logging.info(f'Retrying after {response.headers.get("Retry-After")} seconds')
                else:
                    logging.info(f'There is no Retry-After given in the response header')
                    raise MaxRetryError(_pool, url, error or ResponseError(response.reason))

        return super().increment(method, url, response, error, _pool, _stacktrace)
