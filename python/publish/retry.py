import datetime
import json
import logging

from github import GithubException
from requests import Response
from requests.models import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from urllib3 import Retry, HTTPResponse
from urllib3.exceptions import MaxRetryError

from publish.github_action import GithubAction

logger = logging.getLogger('publish-unit-test-results')


class GitHubRetry(Retry):
    gha: GithubAction = None

    def __init__(self, **kwargs):
        if 'gha' in kwargs:
            self.gha = kwargs['gha']
            del kwargs['gha']

        # 403 is too broad to be retried, but GitHub API signals rate limits via 403
        # we retry 403 and look into the response header via Retry.increment
        kwargs['status_forcelist'] = kwargs.get('status_forcelist', []) + [403]
        super().__init__(**kwargs)

    def new(self, **kw):
        retry = super().new(**kw)
        retry.gha = self.gha
        return retry

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
                self.gha.warning(f'Request {method} {url} failed with 403: {response.reason}')
                if 'Retry-After' in response.headers:
                    logger.info(f'Retrying after {response.headers.get("Retry-After")} seconds')
                else:
                    logger.info(f'There is no Retry-After given in the response header')
                    content = response.reason
                    try:
                        content = get_content(response, url)
                        content = json.loads(content)
                        message = content.get('message', '').lower()

                        if message.startswith('api rate limit exceeded') or \
                                message.endswith('please wait a few minutes before you try again.'):
                            logger.info(f'Response body indicates retry-able error: {message}')
                            for header in ['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset',
                                           'X-RateLimit-Used', 'X-RateLimit-Resource']:
                                if header in response.headers:
                                    value = response.headers.get(header)
                                    logger.debug(f'Response header contains {header}={value}')

                            # backoff until X-RateLimit-Reset
                            if 'X-RateLimit-Reset' in response.headers:
                                value = response.headers.get('X-RateLimit-Reset')
                                if value and value.isdigit():
                                    reset = datetime.datetime.utcfromtimestamp(int(value))
                                    delta = reset - self._utc_now()
                                    retry = super().increment(method, url, response, error, _pool, _stacktrace)
                                    backoff = retry.get_backoff_time()

                                    if delta.total_seconds() > 0:
                                        logger.info(f'Reset occurs in {str(delta)} ({value} / {reset}), '
                                                    f'setting next backoff to {delta.total_seconds()}s')

                                        def get_backoff_time():
                                            # plus 1s as it is not clear when in that second the reset occurs
                                            return max(delta.total_seconds() + 1, backoff)

                                        retry.get_backoff_time = get_backoff_time

                                    return retry

                            return super().increment(method, url, response, error, _pool, _stacktrace)

                        logger.info('Response message does not indicate retry-able error')
                    except MaxRetryError:
                        raise
                    except Exception as e:
                        logger.warning('failed to inspect response message', exc_info=e)

                    raise GithubException(response.status, content, response.headers)

        return super().increment(method, url, response, error, _pool, _stacktrace)

    def _utc_now(self):
        """Used to inject time for testing"""
        return datetime.datetime.utcnow()


def get_content(resp: HTTPResponse, url: str):
    # logic taken from HTTPAdapter.build_response (requests.adapters)
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
