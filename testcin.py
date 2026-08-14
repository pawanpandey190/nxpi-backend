import requests


API_KEY = "579b464db66ec23bdd00000112703593076e438f46c855436f208304"
RESOURCE_ID = "4dbe5667-7b6b-41d7-82af-211562424d9a"

BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"


def verify_cin(cin: str):

    cin = cin.strip().upper()

    params = {
        "api-key": API_KEY,
        "format": "json",
        "filters[CIN]": cin
    }

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30
        )

        print("HTTP Status:", response.status_code)

        response.raise_for_status()

        data = response.json()

        records = data.get("records", [])

        if not records:
            return {
                "verified": False,
                "cin": cin,
                "message": "CIN not found in MCA Company Master Data",
                "data": None
            }

        return {
            "verified": True,
            "cin": cin,
            "message": "CIN verified successfully",
            "data": records[0]
        }

    except requests.exceptions.RequestException as e:

        return {
            "verified": False,
            "cin": cin,
            "message": "API request failed",
            "error": str(e)
        }


if __name__ == "__main__":

    cin = input("Enter CIN:  ")

    result = verify_cin(cin)

    print("\n========== RESULT ==========")
    print(result)
