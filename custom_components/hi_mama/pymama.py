import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag

ATTR_REGEX_DURATION = re.compile("\s\([0-9]{1,2}h[0-9]{1,2}m\)$")
ATTR_REGEX_SPLITTER = re.compile("\s?\-\s?")
ATTR_REGEX_TIME = re.compile("\d{1,2}\:\d{2}[a|p]m")
ATTR_REGEX_CSRF_TOKEN = re.compile('csrf\-token content\="(.+?)"')
ATTR_REGEX_REPORTS = re.compile('\<a href\="\/reports\/(\d+)"\>')
ATTR_DATE_FORMAT = "%A, %b %d, %Y"

session = requests.Session()


def response_noline(url: str) -> str:
    """Given a url, returns a Requests session reponse text with newlines removed"""
    response = session.get(url)
    response = response.text
    response = response.replace("\n", "")
    return response


def flatten_dict(unflat_dict: dict, date: datetime = None):
    """Given a dictionary, will create a generator to flatten into tuple"""
    for key, value in unflat_dict.items():
        if isinstance(value, dict):
            yield from flatten_dict(value, value.get("Date", None))
        if isinstance(value, tuple):
            for rv in reversed(value):
                yield (key, date, rv)


def get_unique_keys(flat_dict: tuple):
    """Given a dictionary flattened into a tuple, will create a generator to return unique values in slice 0"""
    keys = set()
    for fd in flat_dict:
        keys.add(fd[0])
    yield from keys


def get_latest_value(unique_keys, flat_dict):
    """Given unique values as keys and an ordered dictionary, flattened into a tuple, will create generator to return the last value per unique key"""
    for uk in unique_keys:
        for fd in flat_dict:
            if uk in fd[0]:
                yield fd
                break


def report_parser(report):
    if ATTR_REGEX_DURATION.search(report):
        report = ATTR_REGEX_DURATION.sub("", report)
    split_report = ATTR_REGEX_SPLITTER.split(report)
    parsed_tuple = ()
    for piece in split_report:
        if ATTR_REGEX_TIME.search(piece):
            try:
                piece = datetime.strptime(piece, "%I:%M%p").time()
            except:
                pass
        parsed_tuple = parsed_tuple + (piece,)
    return parsed_tuple


def pymama_query(login: str, password: str, child_id: str) -> dict:
    """Given a login, password, and child_id, returns a dict containing all available reports and datapoints in dictionary format"""
    response = response_noline("https://www.himama.com/login")

    csrf_hidden_token = ATTR_REGEX_CSRF_TOKEN.search(response)[1]

    data = [
        ("authenticity_token", csrf_hidden_token),
        ("user[login]", login),
        ("user[password]", password),
        ("commit", "Log In"),
    ]

    response = session.post("https://www.himama.com/login", data=data)
    response = response_noline(f"https://www.himama.com/accounts/{child_id}/reports")

    reports = ATTR_REGEX_REPORTS.finditer(response)

    child_dict = {}

    for i, report in enumerate(reports):
        report_dict = {}

        response = response_noline(f"https://www.himama.com/reports/{report[1]}")
        response = BeautifulSoup(response, "html.parser")

        response_h2 = response.find_all("h2")
        for i2, h2 in enumerate(response_h2):
            h2_text = h2.get_text(strip=True)
            h2_next_siblings = h2.next_sibling.contents
            # TODO: needs refactor
            if i == 0 and i2 == 0:
                child_dict["At Daycare"] = True if "Preview" in h2_text else False
            if "Preview" not in h2_text:
                if "Report" in h2_text:
                    if i == 0:
                        child_dict["Child"] = h2_text.replace("'s Report", "")
                    date_str = h2_next_siblings[0]
                    date_obj = datetime.strptime(date_str, ATTR_DATE_FORMAT)
                    report_dict["Date"] = date_obj
                else:
                    # setup to switch dictionary items to promote Fluids to key
                    report_dict_key = h2_text
                    tuple_default = ()
                    tuple_sub = ()
                    report_dict_value = tuple_default

                    for next_sibling in h2_next_siblings:
                        if isinstance(next_sibling, Tag):
                            if "Fluids" in next_sibling.get_text(strip=True):
                                report_dict_key = "Fluids"
                                report_dict_value = tuple_sub
                                continue
                            report_dict_value = report_dict_value + (
                                report_parser(next_sibling.get_text(strip=True)),
                            )
                        report_dict[report_dict_key] = report_dict_value
        child_dict[f"Report {i}"] = report_dict

    latest_dict = {}

    child_unique_keys = [uk for uk in get_unique_keys(flatten_dict(child_dict.copy()))]
    child_dict_flat = [fd for fd in flatten_dict(child_dict.copy())]

    for lv in get_latest_value(child_unique_keys, child_dict_flat):
        latest_dict[lv[0]] = dict([("Date", lv[1]), ("Value", lv[2])])

    child_dict["Latest"] = latest_dict

    return child_dict


if __name__ == "__main__":
    import sys

    print(pymama_query(sys.argv[1], sys.argv[2], sys.argv[3]))
