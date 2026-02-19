import requests
import os


def verify_userspaces():
    url = "http://localhost:8088/api/userspaces"
    print(f"Fetching userspaces from {url}...")

    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")

    assert username, "ADMIN_USERNAME environment variable must be set"
    assert password, "ADMIN_PASSWORD environment variable must be set"

    try:
        res = requests.get(url, auth=(username, password))
        if res.status_code == 200:
            userspaces = res.json()
            print(f"Userspaces found: {len(userspaces)}")
            for userspace in userspaces:
                print(f"- {userspace}")
        else:
            print(f"Failed to fetch userspaces: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    verify_userspaces()
