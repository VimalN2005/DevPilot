import json
import urllib.request

url = "https://api.github.com/users/VimalN2005/repos?per_page=100"
req = urllib.request.Request(url, headers={"User-Agent": "DevPilot-Installer"})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    non_forks = [r for r in data if not r.get("fork")]
    forks = [r for r in data if r.get("fork")]

    print(f"Total Repos: {len(data)}")
    print(f"Non-Fork Repos: {len(non_forks)}")
    print(f"Fork Repos (Excluded): {len(forks)}\n")

    print("=== Non-Fork Repositories to Install DevPilot Bot ===")
    for r in non_forks:
        print(f"- {r['name']} (Default branch: {r.get('default_branch', 'main')})")
        print(f"  Clone URL: {r.get('clone_url')}")
except Exception as e:
    print(f"Error fetching repos: {e}")
