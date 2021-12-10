import json
import logging

from github import GithubException
from requests import Response
from requests.models import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from urllib3 import Retry, HTTPResponse
from urllib3.exceptions import MaxRetryError, ResponseError

logger = logging.getLogger('publish-unit-test-results')


class GitHubRetry(Retry):
    def __init__(self, **kwargs):
        # 403 is too broad to be retried, but GitHub API signals rate limits via 403
        # we retry 403 and look into the response header via Retry.increment
        kwargs['status_forcelist'] = kwargs.get('status_forcelist', []) + [403]
        super().__init__(**kwargs)

    def increment(self,
                  method=None,
                  url=None,
                  response=None,
                  error=None,
                  _pool=None,
                  _stacktrace=None):
        if response:
            logger.warning(f'Request {method} {url} failed: {response.reason}')
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'Response headers:')
                for field, value in response.headers.items():
                    logger.debug(f'- {field}: {value}')

            # we retry 403 only if there is a Retry-After header (indicating it is retry-able)
            # or if the body message implies so
            if response.status == 403:
                if 'Retry-After' in response.headers:
                    logger.info(f'Retrying after {response.headers.get("Retry-After")} seconds')
                else:
                    logger.info(f'There is no Retry-After given in the response header')
                    content = response.reason
                    try:
                        content = get_content(response, url)
                        content = json.loads(content)
                        message = content.get('message').lower()

                        if message.startswith('api rate limit exceeded') or \
                           message.endswith('please wait a few minutes before you try again.'):
                            logger.info('Response body indicates retry-able error')
                            return super().increment(method, url, response, error, _pool, _stacktrace)

                        logger.info(f'Response message does not indicate retry-able error')
                    except MaxRetryError:
                        raise
                    except Exception as e:
                        logger.warning('failed to inspect response message', exc_info=e)

                    raise GithubException(response.status, content, response.headers)

        return super().increment(method, url, response, error, _pool, _stacktrace)


def get_content(resp: HTTPResponse, url: str):
    response = Response()

    # Fallback to None if there's no status_code, for whatever reason.
    response.status_code = getattr(resp, 'status', None)

    # Make headers case-insensitive.
    response.headers = CaseInsensitiveDict(getattr(resp, 'headers', {}))

    # Set encoding.
    response.encoding = get_encoding_from_headers(response.headers)
    response.raw = resp
    response.reason = response.raw.reason

    response.url = url

    return response.content
