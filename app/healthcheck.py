import json
from urllib import request

"""
This script is used by Docker to do an HEALTHCHECK.
This replace the curl command that is not shipped with docker slim images.
"""

URL = "http://localhost:3500/api/health"
TIMEOUT = 1  # Delay in seconds


def healthcheck():
    """
    Do a GET /Health request to the API and check that it returns {"status": "ok"}.
    Otherwise, it will fail and we will know that the container is unhealthy.
    """
    response = request.urlopen(URL, timeout=TIMEOUT)
    result = json.load(response)
    assert (result["status"]) == "ok"
    return result


def main():
    print(healthcheck())


if __name__ == "__main__":
    main()
