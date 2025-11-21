import requests
from bs4 import BeautifulSoup
import os
import re
from dotenv import load_dotenv


def act_lab_admin_login(su_username: str, su_password: str) -> requests.Session:
    """
    Signs in to www2.dsv.su.se/act-lab/admin via SU SSO login flow

    Args:
        su_username: SU username
        su_password: SU password

    Returns:
        Authenticated session
    """
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

    # 1. Visit the admin page
    response = session.get("https://www2.dsv.su.se/act-lab/admin/")

    # 2. Check if we're redirected to login
    if "idp.it.su.se" in response.url or "login" in response.url.lower():
        # Parse the form if present
        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find("form")

        if form:
            action_url = form.get("action")

            # Extract hidden input fields
            form_data = {
                tag["name"]: tag["value"]
                for tag in form.find_all("input")
                if tag.get("name") and tag.get("value")
            }

            # Add eventId proceed if needed
            if "_eventId_proceed" not in form_data:
                form_data["_eventId_proceed"] = ""

            # Submit the midstep form
            if action_url:
                if not action_url.startswith("http"):
                    action_url = "https://idp.it.su.se" + action_url

                intermediate_response = session.post(action_url, data=form_data)

                # Parse the login form
                soup = BeautifulSoup(intermediate_response.text, "html.parser")
                form = soup.find("form")

                if form:
                    form_data = {
                        tag["name"]: tag.get("value", "") for tag in form.find_all("input")
                    }

                    # Add username and password
                    form_data.update({
                        "j_username": su_username,
                        "j_password": su_password,
                        "_eventId_proceed": "",
                    })

                    # Remove SPNEGO-related keys
                    form_data.pop("_eventId_authn/SPNEGO", None)
                    form_data.pop("_eventId_trySPNEGO", None)

                    # Submit the login form
                    action_url = form["action"]
                    if not action_url.startswith("http"):
                        action_url = "https://idp.it.su.se" + action_url

                    post_response = session.post(action_url, data=form_data)

                    if not post_response.ok:
                        raise AssertionError(f"Login failed with status {post_response.status_code}")

                    # Parse SAML response form
                    soup = BeautifulSoup(post_response.text, "html.parser")
                    form = soup.find("form")

                    if form:
                        # Extract form data (RelayState and SAMLResponse)
                        form_data = {
                            tag.get("name"): tag.get("value")
                            for tag in form.find_all("input")
                            if tag.get("name") and tag.get("value")
                        }

                        # Submit the SAML response
                        action_url = form["action"]
                        session.post(
                            action_url,
                            data=form_data,
                            headers={
                                "Content-Type": "application/x-www-form-urlencoded",
                                "Origin": "https://idp.it.su.se",
                                "Referer": "https://idp.it.su.se/",
                            },
                        )

    return session


def upload_file(session: requests.Session, file_path: str, slide_name: str = "ACT Lab Map") -> bool:
    """
    Upload a file to the ACT lab admin

    Args:
        session: Authenticated session
        file_path: Path to the image file to upload
        slide_name: Name for the uploaded slide

    Returns:
        True if upload was successful
    """
    response = session.get("https://www2.dsv.su.se/act-lab/admin/")

    if response.status_code != 200:
        raise ValueError(f"Failed to access admin page, status code: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the upload form
    upload_form = None
    for form in soup.find_all("form"):
        if form.find("input", attrs={"name": "uploadfile"}):
            upload_form = form
            break

    if not upload_form:
        raise ValueError("Could not find file upload form")

    action = upload_form.get("action")
    if not action.startswith("http"):
        action = "https://www2.dsv.su.se/act-lab/admin/" + action.lstrip("/")

    action_value = upload_form.find("input", attrs={"name": "action"})
    if not action_value:
        raise ValueError("Could not find action field in upload form")

    print(f"Uploading file {os.path.basename(file_path)}...")

    with open(file_path, "rb") as f:
        files = {"uploadfile": (os.path.basename(file_path), f, "image/png")}

        form_data = {
            "action": action_value.get("value"),
            "filename": slide_name
        }

        max_file_size = upload_form.find("input", attrs={"name": "MAX_FILE_SIZE"})
        if max_file_size:
            form_data["MAX_FILE_SIZE"] = max_file_size.get("value", "")

        upload_response = session.post(action, files=files, data=form_data, allow_redirects=True)

        if upload_response.status_code not in [200, 302]:
            print(f"Upload failed. Status: {upload_response.status_code}")
            return False

    print(f"✓ File uploaded successfully!")
    return True


def configure_slide(session: requests.Session, slide_id: str, show_id: str = "1", autodelete: bool = True) -> bool:
    """
    Configure a slide in a show (set auto-delete flag)

    Args:
        session: Authenticated session
        slide_id: ID of the slide to configure
        show_id: ID of the show
        autodelete: Whether to enable auto-delete when removed from show

    Returns:
        True if configuration was successful
    """
    response = session.get("https://www2.dsv.su.se/act-lab/admin/")
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the configure_slide form for this slide
    configure_form = None
    for form in soup.find_all("form"):
        action_input = form.find("input", attrs={"name": "action", "value": "configure_slide"})
        slideid_input = form.find("input", attrs={"name": "slideid", "value": slide_id})
        if action_input and slideid_input:
            configure_form = form
            break

    if not configure_form:
        print(f"Could not find configure form for slide {slide_id}")
        return False

    action = configure_form.get("action")
    if not action.startswith("http"):
        action = "https://www2.dsv.su.se/act-lab/admin/" + action.lstrip("/")

    form_data = {
        "action": "configure_slide",
        "showid": show_id,
        "slideid": slide_id,
        "starttime": "",
        "endtime": ""
    }

    if autodelete:
        form_data["autodelete"] = "on"

    config_response = session.post(action, data=form_data, allow_redirects=True)

    if config_response.status_code in [200, 302]:
        print(f"✓ Slide configured with auto-delete enabled")
        return True
    else:
        print(f"Failed to configure slide. Status: {config_response.status_code}")
        return False


def remove_old_slides_from_show(session: requests.Session, show_id: str = "1", keep_latest: int = 1) -> int:
    """
    Remove old slides from a show, keeping only the most recent ones

    Args:
        session: Authenticated session
        show_id: ID of the show to remove slides from
        keep_latest: Number of most recent slides to keep (default: 1)

    Returns:
        Number of slides removed
    """
    response = session.get("https://www2.dsv.su.se/act-lab/admin/")
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the show section
    show_section = soup.find("div", id=show_id, class_="show")
    if not show_section:
        print(f"Could not find show {show_id}")
        return 0

    # Find all slides in this show
    slides_in_show = show_section.find_all("div", class_="slide")

    if len(slides_in_show) <= keep_latest:
        print(f"Show has {len(slides_in_show)} slide(s), keeping all")
        return 0

    # Get slide IDs and sort by ID (higher ID = more recent)
    slide_ids = []
    for slide in slides_in_show:
        slide_id = slide.get("id")
        if slide_id:
            slide_ids.append(int(slide_id))

    slide_ids.sort(reverse=True)

    # Remove all but the most recent ones
    slides_to_remove = slide_ids[keep_latest:]

    print(f"Found {len(slides_in_show)} slide(s) in show, keeping {keep_latest} most recent")

    removed_count = 0
    for slide_id in slides_to_remove:
        print(f"Removing old slide {slide_id} from show...")

        # Find the remove form
        remove_form = None
        for form in soup.find_all("form"):
            if form.get("name") == "remove":
                remove_form = form
                break

        if remove_form:
            action = remove_form.get("action")
            if not action.startswith("http"):
                action = "https://www2.dsv.su.se/act-lab/admin/" + action.lstrip("/")

            form_data = {
                "action": "remove",
                "remove": str(slide_id),
                "from": show_id
            }

            remove_response = session.post(action, data=form_data, allow_redirects=True)

            if remove_response.status_code in [200, 302]:
                print(f"✓ Removed slide {slide_id}")
                removed_count += 1
                # Refresh the page for next iteration
                response = session.get("https://www2.dsv.su.se/act-lab/admin/")
                soup = BeautifulSoup(response.text, "html.parser")
                show_section = soup.find("div", id=show_id, class_="show")

    return removed_count


def add_slide_to_show(session: requests.Session, show_id: str = "1") -> bool:
    """
    Add the most recently uploaded slide to a show

    Args:
        session: Authenticated session
        show_id: ID of the show to add the slide to (default: "1" for Labbet)

    Returns:
        True if slide was added successfully
    """
    response = session.get("https://www2.dsv.su.se/act-lab/admin/")
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the highest slide ID (most recent)
    all_slide_ids = re.findall(r'<div class="slide"\s+id="(\d+)"', response.text)
    if not all_slide_ids:
        print("No slides found")
        return False

    slide_id = max(all_slide_ids, key=int)
    print(f"Adding most recent slide (ID: {slide_id}) to show {show_id}...")

    # Find the form to add slide to show
    add_form = None
    for form in soup.find_all("form"):
        if form.find("input", attrs={"name": "add"}) and form.find("input", attrs={"name": "to"}):
            add_form = form
            break

    if not add_form:
        print("Could not find form to add slide to show")
        return False

    action = add_form.get("action")
    if not action.startswith("http"):
        action = "https://www2.dsv.su.se/act-lab/admin/" + action.lstrip("/")

    action_value = add_form.find("input", attrs={"name": "action"})

    form_data = {
        "action": action_value.get("value"),
        "add": slide_id,
        "to": show_id
    }

    add_response = session.post(action, data=form_data, allow_redirects=True)

    if add_response.status_code in [200, 302]:
        print(f"✓ Slide added to show successfully!")

        # Configure the slide with auto-delete enabled
        configure_slide(session, slide_id, show_id, autodelete=True)

        return True
    else:
        print(f"Failed to add slide to show. Status: {add_response.status_code}")
        return False


if __name__ == "__main__":
    load_dotenv()

    su_username = os.getenv("SU_USERNAME")
    su_password = os.getenv("SU_PASSWORD")

    if not su_username or not su_password:
        raise ValueError("SU_USERNAME and SU_PASSWORD must be set in .env file")

    file_path = "output/tv/ACT_map_tv.png"
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    print("Logging in to ACT Lab admin...")
    session = act_lab_admin_login(su_username, su_password)

    # First, remove old slides from the show (keep only 0 = remove all before adding new one)
    print("\nChecking for old slides to remove...")
    removed = remove_old_slides_from_show(session, show_id="1", keep_latest=0)
    if removed > 0:
        print(f"✓ Removed {removed} old slide(s)")
    else:
        print("No old slides to remove")

    # Upload the new file
    if upload_file(session, file_path):
        # Add it to the show with auto-delete enabled
        add_slide_to_show(session)
        print("\n✓ Upload and setup completed successfully!")
    else:
        print("\n✗ Upload failed")
