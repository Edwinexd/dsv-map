import requests
from bs4 import BeautifulSoup
from cookie_cache import get_cached_cookie, save_cookie_to_cache


def daisy_staff_login(su_username: str, su_password: str, use_cache: bool = True) -> str:
    """
    Signs in to Daisy via SU login flow (staff login) and returns the JSESSIONID cookie value

    Args:
        su_username: SU username
        su_password: SU password
        use_cache: Whether to use cached cookies (default: True)

    Returns:
        JSESSIONID cookie value for Daisy
    """
    # Check cache first
    if use_cache:
        cached_cookie = get_cached_cookie("daisy_staff")
        if cached_cookie:
            return cached_cookie

    # Start a session to keep cookies
    session = requests.Session()

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8,sv;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        "sec-ch-ua": '"Microsoft Edge";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "X-Powered-By": "dsv-staff-map (https://github.com/Edwinexd/dsv-staff-map); Contact (edwinsu@dsv.su.se)",
    }
    for key, value in headers.items():
        session.headers[key] = value

    # 1. Get the initial session cookie by visiting the main page
    session.get("https://daisy.dsv.su.se/index.jspa")

    # 2. Navigate to the staff login URL
    login_response = session.get(
        "https://daisy.dsv.su.se/Shibboleth.sso/Login?entityID=https://idp.it.su.se/idp/shibboleth&target=https://daisy.dsv.su.se/login_sso_employee.jspa"
    )

    # 3. Parse the first form (auto-submit form)
    soup = BeautifulSoup(login_response.text, "html.parser")
    form = soup.find("form")
    action_url = form["action"]

    # Extract hidden input fields
    form_data = {
        tag["name"]: tag["value"]
        for tag in form.find_all("input")
        if tag.get("name") and tag.get("value")
    }

    # Add eventId proceed
    form_data.update({"_eventId_proceed": ""})

    # 4. Submit the midstep form
    intermediate_response = session.post(
        "https://idp.it.su.se" + action_url, data=form_data
    )

    # 5. Parse the login form
    soup = BeautifulSoup(intermediate_response.text, "html.parser")
    form = soup.find("form")

    if not form:
        raise ValueError("No login form found")

    form_data = {
        tag["name"]: tag.get("value", "") for tag in form.find_all("input")
    }

    # Add username and password
    form_data.update(
        {
            "j_username": su_username,
            "j_password": su_password,
            "_eventId_proceed": "",
        }
    )

    # Remove SPNEGO-related keys
    form_data.pop("_eventId_authn/SPNEGO", None)
    form_data.pop("_eventId_trySPNEGO", None)

    # 6. Submit the login form
    action_url = form["action"]
    post_response = session.post(
        "https://idp.it.su.se" + action_url, data=form_data
    )

    if not post_response.ok:
        raise AssertionError(f"Login failed with status {post_response.status_code}")

    # 7. Parse SAML response form
    soup = BeautifulSoup(post_response.text, "html.parser")
    form = soup.find("form")

    # Extract form data (RelayState and SAMLResponse)
    form_data = {
        tag.get("name"): tag.get("value")
        for tag in form.find_all("input")
        if tag.get("name") and tag.get("value")
    }

    # 8. Submit the SAML response
    action_url = form["action"]
    post_response = session.post(
        action_url,
        data=form_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://idp.it.su.se",
            "Referer": "https://idp.it.su.se/",
        },
    )

    # 9. Extract JSESSIONID from cookies for daisy.dsv.su.se
    jsessionid = None
    for cookie in session.cookies:
        if cookie.name == "JSESSIONID" and "daisy.dsv.su.se" in cookie.domain:
            jsessionid = cookie.value
            break

    if not jsessionid:
        raise ValueError("Failed to obtain JSESSIONID cookie for daisy.dsv.su.se")

    # Cache the cookie
    if use_cache:
        save_cookie_to_cache("daisy_staff", jsessionid)

    return jsessionid
