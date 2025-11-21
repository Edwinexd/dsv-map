import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from cookie_cache import get_cached_cookie, save_cookie_to_cache


def mobil_handledning_login(su_username: str, su_password: str, use_cache: bool = True) -> str:
    """
    Signs in to mobil.handledning.dsv.su.se via SU login flow and returns the JSESSIONID cookie value

    Args:
        su_username: SU username
        su_password: SU password
        use_cache: Whether to use cached cookies (default: True)

    Returns:
        JSESSIONID cookie value
    """
    # Check cache first
    if use_cache:
        cached_cookie = get_cached_cookie("mobil_handledning")
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
    main_page_response = session.get("https://mobil.handledning.dsv.su.se/")

    # 2. Parse the main page to get the Stockholm University login link
    soup = BeautifulSoup(main_page_response.text, "html.parser")
    # Find the link with text "Stockholm University account"
    su_login_link = None
    for link in soup.find_all("a"):
        if "Stockholm University account" in link.get_text():
            su_login_link = link.get("href")
            break

    if not su_login_link:
        raise ValueError("Could not find Stockholm University login link on main page")

    # Make the link absolute if it's relative
    if su_login_link.startswith("/"):
        su_login_link = "https://mobil.handledning.dsv.su.se" + su_login_link

    # 3. Navigate to the Stockholm University login URL
    login_response = session.get(su_login_link)

    # 4. Parse the first form (auto-submit form)
    soup = BeautifulSoup(login_response.text, "html.parser")
    form = soup.find("form")
    action_url = form["action"]

    # Extract hidden input fields
    form_data = {
        tag["name"]: tag["value"]
        for tag in form.find_all("input")
        if tag.get("name") and tag.get("value")
    }

    # Add eventId proceed as it doesn't have a value
    form_data.update(
        {
            "_eventId_proceed": "",
        }
    )

    # 5. Submit the midstep form manually (this mimics JavaScript auto-submit)
    intermediate_response = session.post(
        "https://idp.it.su.se" + action_url, data=form_data
    )

    # 6. Parse the login form
    soup = BeautifulSoup(intermediate_response.text, "html.parser")
    form = soup.find("form")

    if not form:
        raise ValueError("No login form found")

    form_data = {
        tag["name"]: tag.get("value", "") for tag in form.find_all("input")
    }

    # Add username and password to the form data
    form_data.update(
        {
            "j_username": su_username,
            "j_password": su_password,
            "_eventId_proceed": "",
        }
    )

    # Remove SPNEGO-related keys if present
    form_data.pop("_eventId_authn/SPNEGO", None)
    form_data.pop("_eventId_trySPNEGO", None)

    # 7. Submit the login form
    action_url = form["action"]
    post_response = session.post(
        "https://idp.it.su.se" + action_url, data=form_data
    )

    if not post_response.ok:
        raise AssertionError(f"Login failed with status {post_response.status_code}")

    # 8. Parse SAML response form
    soup = BeautifulSoup(post_response.text, "html.parser")
    form = soup.find("form")

    # Extract form data (RelayState and SAMLResponse)
    form_data = {
        tag.get("name"): tag.get("value")
        for tag in form.find_all("input")
        if tag.get("name") and tag.get("value")
    }

    # 9. Submit the SAML response
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

    # 10. Extract JSESSIONID from cookies for mobil.handledning.dsv.su.se
    jsessionid = None
    for cookie in session.cookies:
        if cookie.name == "JSESSIONID" and "mobil.handledning.dsv.su.se" in cookie.domain:
            jsessionid = cookie.value
            break

    if not jsessionid:
        raise ValueError("Failed to obtain JSESSIONID cookie for mobil.handledning.dsv.su.se")

    # Cache the cookie
    if use_cache:
        save_cookie_to_cache("mobil_handledning", jsessionid)

    return jsessionid


def handledning_login(su_username: str, su_password: str, use_cache: bool = True) -> str:
    """
    Signs in to handledning.dsv.su.se (desktop version) via SU login flow and returns the JSESSIONID cookie value

    Args:
        su_username: SU username
        su_password: SU password
        use_cache: Whether to use cached cookies (default: True)

    Returns:
        JSESSIONID cookie value
    """
    # Check cache first
    if use_cache:
        cached_cookie = get_cached_cookie("handledning")
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
    main_page_response = session.get("https://handledning.dsv.su.se/")

    # 2. Parse the main page to get the Stockholm University login link
    soup = BeautifulSoup(main_page_response.text, "html.parser")
    # Find the link with "Stockholms universitetskonto" or "Stockholm University account"
    su_login_link = None
    for link in soup.find_all("a"):
        link_text = link.get_text()
        if "Stockholm" in link_text and ("universitet" in link_text.lower() or "University" in link_text):
            su_login_link = link.get("href")
            break

    if not su_login_link:
        raise ValueError("Could not find Stockholm University login link on main page")

    # Make the link absolute if it's relative
    if su_login_link.startswith("/"):
        su_login_link = "https://handledning.dsv.su.se" + su_login_link

    # 3. Navigate to the Stockholm University login URL
    login_response = session.get(su_login_link)

    # 4. Parse the first form (auto-submit form)
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

    # 5. Submit the midstep form
    intermediate_response = session.post(
        "https://idp.it.su.se" + action_url, data=form_data
    )

    # 6. Parse the login form
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

    # 7. Submit the login form
    action_url = form["action"]
    post_response = session.post(
        "https://idp.it.su.se" + action_url, data=form_data
    )

    if not post_response.ok:
        raise AssertionError(f"Login failed with status {post_response.status_code}")

    # 8. Parse SAML response form
    soup = BeautifulSoup(post_response.text, "html.parser")
    form = soup.find("form")

    # Extract form data (RelayState and SAMLResponse)
    form_data = {
        tag.get("name"): tag.get("value")
        for tag in form.find_all("input")
        if tag.get("name") and tag.get("value")
    }

    # 9. Submit the SAML response
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

    # 10. Extract JSESSIONID from cookies for handledning.dsv.su.se
    jsessionid = None
    for cookie in session.cookies:
        if cookie.name == "JSESSIONID" and "handledning.dsv.su.se" in cookie.domain:
            jsessionid = cookie.value
            break

    if not jsessionid:
        raise ValueError("Failed to obtain JSESSIONID cookie for handledning.dsv.su.se")

    # Cache the cookie
    if use_cache:
        save_cookie_to_cache("handledning", jsessionid)

    return jsessionid


def activate_all_lists(cookies_dict: Dict[str, str]) -> int:
    """
    Activates all inactive lists for the current user

    Args:
        cookies_dict: Dictionary containing JSESSIONID cookie for mobil.handledning.dsv.su.se

    Returns:
        Number of lists activated
    """
    headers = {
        "X-Powered-By": "dsv-staff-map (https://github.com/Edwinexd/dsv-staff-map); Contact (edwinsu@dsv.su.se)",
    }

    # Get list of teachers/lists (only works if already active on at least one list)
    response = requests.get(
        "https://mobil.handledning.dsv.su.se/servlet/GetListTeachersServlet",
        cookies=cookies_dict,
        timeout=5,
        headers=headers
    )

    if response.status_code != 200:
        raise ValueError(f"Failed to get list of teachers, status code: {response.status_code}")

    # Parse HTML to find inactive lists
    soup = BeautifulSoup(response.text, "html.parser")
    activation_links = []

    for link in soup.find_all("a"):
        if "Aktivera" in link.get_text() and "SetListTeacherActiveServlet" in link.get("href", ""):
            activation_links.append(link.get("href"))

    # Activate each inactive list
    activated_count = 0
    for link in activation_links:
        full_url = "https://mobil.handledning.dsv.su.se" + link
        activate_response = requests.get(
            full_url,
            cookies=cookies_dict,
            timeout=5,
            headers=headers
        )
        if activate_response.status_code == 200:
            activated_count += 1

    return activated_count


def get_mobile_schedules(cookies_dict: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Fetch planned tutoring schedules from the mobile handledning site

    Args:
        cookies_dict: Dictionary containing JSESSIONID cookie for mobil.handledning.dsv.su.se

    Returns:
        List of dictionaries with schedule information:
        - course: Course name/code
        - start_time: Start datetime
        - end_time: End datetime
        - list_id: Associated list ID (from listteacherid)
    """
    headers = {
        "X-Powered-By": "dsv-staff-map (https://github.com/Edwinexd/dsv-staff-map); Contact (edwinsu@dsv.se)",
    }

    # Fetch the list of teachers/lists page which shows active lists
    response = requests.get(
        "https://mobil.handledning.dsv.su.se/servlet/GetListTeachersServlet",
        cookies=cookies_dict,
        timeout=10,
        headers=headers
    )

    if response.status_code != 200:
        raise ValueError(f"Failed to fetch mobile schedules, status code: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")
    schedules = []

    import re
    from datetime import datetime, timedelta

    # Parse structure:
    # <td class="small">
    #   Handledning
    #   CPROG
    #   13:00-15:00<br />
    #   Mitt schema:
    #   13:00-15:00 <br />
    #   Ange Zoom-ID
    # </td>

    # Find all td elements with class="small" that contain schedule info
    for td in soup.find_all("td", class_="small"):
        td_text = td.get_text()

        # Look for "Mitt schema:" which indicates this is an active list entry
        if "Mitt schema:" not in td_text:
            continue

        # Extract course code (typically appears before the time)
        # Look for a word in all caps or a course code pattern
        course_match = re.search(r'\b([A-Z]{3,}[A-Z0-9]*)\b', td_text)
        course_name = course_match.group(1) if course_match else "Unknown"

        # Find the time AFTER "Mitt schema:" (this is YOUR scheduled time)
        # Split by "Mitt schema:" and look in the second part
        parts = td_text.split("Mitt schema:")
        if len(parts) < 2:
            continue

        my_schedule_part = parts[1]

        # Look for time pattern in "Mitt schema" section
        time_match = re.search(r'(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})', my_schedule_part)
        if not time_match:
            continue

        # Extract time
        start_hour = int(time_match.group(1))
        start_min = int(time_match.group(2))
        end_hour = int(time_match.group(3))
        end_min = int(time_match.group(4))

        # Find list teacher ID from the deactivate link in the same row
        parent_row = td.find_parent("tr")
        list_id = None
        if parent_row:
            # Look for link with listteacherid parameter
            link = parent_row.find("a", href=re.compile(r"listteacherid=\d+"))
            if link:
                listid_match = re.search(r"listteacherid=(\d+)", link.get("href"))
                if listid_match:
                    list_id = listid_match.group(1)

        # Create datetime objects for today at the specified times
        now = datetime.now()
        start_time = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        end_time = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

        # If the end time is before the start time, it crosses midnight
        if end_time < start_time:
            end_time += timedelta(days=1)

        schedules.append({
            "course": course_name,
            "start_time": start_time,
            "end_time": end_time,
            "list_id": list_id
        })

    return schedules


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


def daisy_search_student(cookies_dict: Dict[str, str], search_string: str) -> List[Dict[str, str]]:
    """
    Search for a student in Daisy

    Args:
        cookies_dict: Dictionary containing JSESSIONID cookie for Daisy
        search_string: Student name or partial name to search for

    Returns:
        List of dictionaries containing student information with keys:
        - lastname: Student last name
        - firstname: Student first name
        - email: Student email
        - profile_url: URL to student profile
        - schedule_url: URL to student schedule
    """
    headers = {
        "X-Powered-By": "dsv-staff-map (https://github.com/Edwinexd/dsv-staff-map); Contact (edwinsu@dsv.su.se)",
    }

    # Parse search string into firstname and lastname
    parts = search_string.strip().split()
    if len(parts) >= 2:
        fornamn = parts[0]
        efternamn = " ".join(parts[1:])
    else:
        fornamn = ""
        efternamn = search_string

    # Perform the search via POST
    response = requests.post(
        "https://daisy.dsv.su.se/sok/visastudent.jspa",
        cookies=cookies_dict,
        data={
            "efternamn": efternamn,
            "fornamn": fornamn,
            "action:sokstudent": "Sök"
        },
        timeout=10,
        headers=headers
    )

    if response.status_code != 200:
        raise ValueError(f"Failed to search student, status code: {response.status_code}")

    # Parse the HTML response
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the results table with class "randig"
    results = []
    table = soup.find("table", class_="randig")

    if table:
        rows = table.find_all("tr")[1:]  # Skip header row
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 5:
                student_info = {}

                # Col 0: Link to profile
                profile_link = cols[0].find("a")
                if profile_link:
                    student_info["profile_url"] = profile_link.get("href", "")

                # Col 1: Link to schedule
                schedule_link = cols[1].find("a")
                if schedule_link:
                    student_info["schedule_url"] = schedule_link.get("href", "")

                # Col 2: Lastname
                student_info["lastname"] = cols[2].get_text().strip()

                # Col 3: Firstname
                student_info["firstname"] = cols[3].get_text().strip()

                # Col 4: Email
                student_info["email"] = cols[4].get_text().strip()

                # Full name
                student_info["name"] = f"{student_info['firstname']} {student_info['lastname']}"

                if student_info["lastname"] or student_info["firstname"]:
                    results.append(student_info)

    return results


def get_list_info_for_student(handledning_cookies: Dict[str, str], student_name: str) -> Optional[Dict[str, str]]:
    """
    Find which list a student is currently on and fetch detailed information about that list

    Args:
        handledning_cookies: Dictionary containing JSESSIONID cookie for handledning.dsv.su.se
        student_name: Name of the student to search for (can include " i location" part)

    Returns:
        Dictionary with list information or None if not found:
        - listid: The list ID
        - student_name: Clean student name (without location)
        - location: Student location (if specified)
        - course: Course name/code
        - other_teachers: List of other teachers who have helped students
        - recent_activity: Summary of recent activity
    """
    headers = {
        "X-Powered-By": "dsv-staff-map (https://github.com/Edwinexd/dsv-staff-map); Contact (edwinsu@dsv.su.se)",
    }

    # Get teacher start page with today's lists
    response = requests.get(
        "https://handledning.dsv.su.se/teacher/",
        cookies=handledning_cookies,
        timeout=10,
        headers=headers
    )

    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # Find all list IDs and their associated tables
    import re

    # Search through all tables for the student name
    tables = soup.find_all("table")

    for table in tables:
        # Check if this table contains the student name
        table_text = table.get_text()
        if student_name in table_text:
            # Try to find the row with the student
            rows = table.find_all("tr")
            student_clean_name = None
            student_location = None

            for row in rows:
                row_text = row.get_text()
                if student_name in row_text:
                    # Try to extract clean name and location from the row
                    cells = row.find_all("td")
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        # Look for pattern "Name i Location" or just "Name"
                        if " i " in cell_text:
                            parts = cell_text.split(" i ", 1)
                            student_clean_name = parts[0].strip()
                            student_location = parts[1].strip() if len(parts) > 1 else None
                            break
                        elif student_name in cell_text:
                            student_clean_name = cell_text.strip()
                            break
                    if student_clean_name:
                        break

            # Look for a link with listid in the same or nearby table/section
            # Search in parent elements
            parent = table.find_parent("td")
            if not parent:
                parent = table.find_parent("tr")
            if not parent:
                parent = table

            # Find any links with listid
            links = parent.find_all("a", href=re.compile(r"listid=\d+"))
            if not links:
                # Try searching the whole table
                links = table.find_all("a", href=re.compile(r"listid=\d+"))

            if links:
                # Extract listid from first link
                match = re.search(r"listid=(\d+)", links[0].get("href"))
                if match:
                    listid = match.group(1)

                    # Fetch detailed list information
                    list_url = f"https://handledning.dsv.su.se/servlet/teacher/GetListServlet?listid={listid}"
                    list_response = requests.get(list_url, cookies=handledning_cookies, timeout=10, headers=headers)

                    if list_response.status_code == 200:
                        info = parse_list_details(list_response.text, listid)
                        # Add the clean student name and location if we found it
                        if student_clean_name:
                            info["student_name"] = student_clean_name
                        if student_location:
                            info["location"] = student_location
                        return info

    return None


def get_planned_schedules(handledning_cookies: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Fetch planned tutoring schedules for the logged-in teacher

    Args:
        handledning_cookies: Dictionary containing JSESSIONID cookie for handledning.dsv.su.se

    Returns:
        List of dictionaries with schedule information:
        - course: Course name/code
        - start_time: Start datetime
        - end_time: End datetime
        - location: Location (if available)
        - list_id: Associated list ID
    """
    headers = {
        "X-Powered-By": "dsv-staff-map (https://github.com/Edwinexd/dsv-staff-map); Contact (edwinsu@dsv.su.se)",
    }

    # Fetch teacher page with filter for planned lists only (lists where you are scheduled)
    response = requests.get(
        "https://handledning.dsv.su.se/teacher/?onlyown=yes",
        cookies=handledning_cookies,
        timeout=10,
        headers=headers
    )

    if response.status_code != 200:
        raise ValueError(f"Failed to fetch planned schedules, status code: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")
    schedules = []

    import re
    from datetime import datetime

    # First, find all "Mina tider" time ranges with their associated dates
    # Maps (date, time_tuple) -> True for sessions where you're scheduled
    mina_tider_entries = {}

    # Iterate through all elements containing "Mina tider"
    for elem in soup.find_all(string=lambda text: text and 'Mina tider' in text):
        parent_td = elem.find_parent('td')
        if parent_td and parent_td.get('colspan'):  # Mina tider is in a colspan td
            # Extract time ranges from this cell only
            cell_text = parent_td.get_text()
            # Only add times that appear AFTER "Mina tider:" text
            if 'Mina tider' in cell_text:
                # Split at "Mina tider:" and only look at the part after
                after_mina_tider = cell_text.split('Mina tider', 1)[1]
                time_ranges_after = re.findall(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', after_mina_tider)

                # Find the date associated with this "Mina tider" entry
                # Look at the previous row in the table to find the date
                parent_row = parent_td.find_parent('tr')
                if parent_row:
                    # Look at previous sibling rows to find the date
                    current_row = parent_row
                    date_str = None
                    while current_row:
                        # Check cells in this row for a date
                        cells = current_row.find_all('td')
                        for cell in cells:
                            cell_text_check = cell.get_text(strip=True)
                            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', cell_text_check)
                            if date_match:
                                date_str = date_match.group(1)
                                break
                        if date_str:
                            break
                        # Move to previous row
                        current_row = current_row.find_previous_sibling('tr')

                    # Store the time ranges with the associated date
                    if date_str:
                        for time_range in time_ranges_after:
                            mina_tider_entries[(date_str, time_range)] = True

    # Debug: Print what "Mina tider" entries were found (if any)
    # Uncomment for debugging:
    # if mina_tider_entries:
    #     print(f"Found {len(mina_tider_entries)} Mina tider entries:")
    #     for (date, time_tuple) in sorted(mina_tider_entries.keys()):
    #         print(f"  {date} {time_tuple[0]}:{time_tuple[1]}-{time_tuple[2]}:{time_tuple[3]}")

    # Find the main table with schedule information
    # Look for table with headers like "Listtyp", "Datum", "Tid", "Kurser"
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")

        # Check if this is the schedule table by looking for header row
        if not rows:
            continue

        header_row = rows[0]
        header_text = header_row.get_text()

        # Check if this table has the expected headers
        if "Datum" not in header_text or "Tid" not in header_text:
            continue

        # Found the schedule table, parse data rows
        for row in rows[1:]:  # Skip header row
            cells = row.find_all("td")

            if len(cells) < 4:  # Need at least: Listtyp, Datum, Tid, Kurser
                continue

            try:
                # Column 0: List type (e.g., "Handledning")
                list_type = cells[0].get_text(strip=True)

                # Column 1: Date (format: YYYY-MM-DD)
                date_str = cells[1].get_text(strip=True)
                if not date_str or not re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                    continue

                # Column 2: Time range (format: "HH:MM - HH:MM")
                time_str = cells[2].get_text(strip=True)
                time_match = re.search(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', time_str)
                if not time_match:
                    continue

                # Column 3: Courses (format: "[ CPROG ]" or multiple courses)
                courses_str = cells[3].get_text(strip=True)
                # Extract course codes from brackets
                course_codes = re.findall(r'\[\s*([^\]]+?)\s*\]', courses_str)
                course_name = ", ".join(course_codes) if course_codes else list_type

                # Column 4: Comments/notes (e.g., "Ange Zoom-ID")
                comments = cells[4].get_text(strip=True) if len(cells) > 4 else ""

                # Parse date
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")

                # Parse time
                start_hour = int(time_match.group(1))
                start_min = int(time_match.group(2))
                end_hour = int(time_match.group(3))
                end_min = int(time_match.group(4))

                start_time = date_obj.replace(hour=start_hour, minute=start_min)
                end_time = date_obj.replace(hour=end_hour, minute=end_min)

                # Only include this schedule if it matches a "Mina tider" entry for this date+time
                # time_tuple format: ('10', '00', '12', '00') from the regex match
                time_tuple = (time_match.group(1), time_match.group(2),
                             time_match.group(3), time_match.group(4))

                if mina_tider_entries and (date_str, time_tuple) not in mina_tider_entries:
                    # Skip this schedule - not in "Mina tider" for this date
                    continue

                # Try to find list ID from any links in the row
                list_id = None
                for cell in cells:
                    link = cell.find("a", href=re.compile(r"listid=\d+"))
                    if link:
                        listid_match = re.search(r"listid=(\d+)", link.get("href"))
                        if listid_match:
                            list_id = listid_match.group(1)
                            break

                schedules.append({
                    "course": course_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": comments if comments else "",
                    "list_id": list_id,
                    "list_type": list_type
                })

            except (ValueError, IndexError) as e:
                # Skip rows that don't parse correctly
                continue

    # Remove duplicates based on list_id, start_time, and end_time
    seen = set()
    unique_schedules = []
    for schedule in schedules:
        # Create a unique key for deduplication
        key = (schedule["list_id"], schedule["start_time"], schedule["end_time"])
        if key not in seen:
            seen.add(key)
            unique_schedules.append(schedule)

    return unique_schedules


def parse_list_details(html: str, listid: str) -> Dict[str, str]:
    """Parse list details HTML and extract relevant information"""
    soup = BeautifulSoup(html, "html.parser")

    info = {
        "listid": listid,
        "course": "",
        "other_teachers": [],
        "recent_activity": ""
    }

    # Extract course information
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                header = cells[0].get_text().strip()
                if "Kurskod" in header or "Kursnamn" in header:
                    # Found course table
                    if len(cells) > 1:
                        info["course"] = cells[1].get_text().strip()
                    break

    # Extract teachers who have helped (from history table)
    # Look for patterns like "HH:MM:SS-HH:MM:SS Teacher Name"
    import re
    teacher_pattern = re.compile(r'\d{2}:\d{2}:\d{2}-\d{2}:\d{2}:\d{2}\s+([^<(]+?)(?:\s*\(|<br|$)')

    teachers_found = set()
    matches = teacher_pattern.findall(html)
    for match in matches:
        teacher_name = match.strip()
        if teacher_name and teacher_name not in teachers_found:
            teachers_found.add(teacher_name)

    info["other_teachers"] = sorted(list(teachers_found))

    # Get recent activity summary (last few entries from history)
    activity_lines = []
    history_table = None

    for table in tables:
        # Look for tables with student names and timestamps
        text = table.get_text()
        if re.search(r'\d{2}:\d{2}:\d{2}', text):
            history_table = table
            break

    if history_table:
        rows = history_table.find_all("tr")
        # Get last 3 entries (skip header)
        for row in rows[-3:]:
            cells = row.find_all("td")
            if len(cells) >= 2:
                time = cells[0].get_text().strip()
                student = cells[1].get_text().strip()
                if time and student and re.match(r'\d{2}:\d{2}', time):
                    activity_lines.append(f"{time} - {student}")

    info["recent_activity"] = "; ".join(activity_lines) if activity_lines else "No recent activity"

    return info



