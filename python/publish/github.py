import logging

from github import Requester, RateLimitExceededException, GithubException
from requests import Response
from requests.models import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from urllib3 import Retry, HTTPResponse
from urllib3.exceptions import MaxRetryError, ResponseError


logger = logging.getLogger('publish-unit-test-results')


class GitHubRetry(Retry):
    requester: Requester = None

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
            if logger.isEnabledFor(logging.DEBUG):
                logging.debug(f'Response headers:')
                for field, value in response.headers.items():
                    logging.debug(f'- {field}: {value}')

            # we retry 403 only if there is a Retry-After header (indicating it is retry-able)
            # or if we know it is a rate limit exceeded exception (which might not have a Retry-After header)
            if response.status == 403:
                if 'Retry-After' in response.headers:
                    logging.info(f'Retrying after {response.headers.get("Retry-After")} seconds')
                else:
                    logging.info(f'There is no Retry-After given in the response header')
                    try:
                        output = get_content(response, url)
                        #output = json.loads(output)

                        if self.requester is not None:
                            try:
                                self.requester._Requester__check(response.status, response.headers, output)
                            except RateLimitExceededException:
                                return super().increment(method, url, response, error, _pool, _stacktrace)
                            except GithubException as e:
                                raise e

                            #if output.get("message").lower().startswith("api rate limit exceeded")
                            #    or output.get("message")
                            #    .lower()
                            #    .endswith("please wait a few minutes before you try again.")
                    except GithubException as e:
                        raise e
                    except:
                        pass

                    raise MaxRetryError(_pool, url, error or ResponseError(response.reason))

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
