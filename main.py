import os
import sys

from bs4 import BeautifulSoup
import httpx

def read_from_file(filename: str) -> str:
    with open(filename) as f:
        return f.read()

def read_from_url(url: str) -> str:
    print(f"Baixando dados de {url}...")
    req = httpx.request("GET", url)
    if req.status_code != 200:
        raise RuntimeError(f"request returned {req.status_code}")
    return req.read().decode()

def main():
    team_id = input("Time ID do transfermarkt: ")
    verein_id = input("Time ID serial (verein) do transfermarkt: ")
    year = int(input("Ano de transferências: "))

    url = f"https://www.transfermarkt.com/{team_id}/kader/verein/{verein_id}/saison_id/{year-1}/plus/1"
    html: str

    # when in debug mode, fetch html data from cache folder
    # (in order not to send a ton of requests while just debugging)
    if "debug" in sys.argv[1]:
        print("--- DEBUG MODE ---")

        if not os.path.exists("samples/"):
            os.mkdir("samples")

        filepath = f"samples/{team_id}{verein_id}{year}.html"
        if not os.path.exists(filepath):
            html = read_from_url(url)
            with open(filepath, "w") as f:
                f.write(html)
        else:
            html = read_from_file(filepath)
    else:
        html = read_from_url(url)

    soup = BeautifulSoup(html, "html.parser")

    team = soup.find("header", {"class": "data-header"}).find("h1", {"class": "data-header__headline-wrapper"}).string.strip()
    print(f"Transferências de {team} em {year}:")

    # all the data is inside the zentriet class table items
    results = soup.find_all("td", {"class": "zentriert"})
    for elem in results:
        # find joined date (it won't collide with birth date. fortunately no player is that young)
        if elem.string is not None and str(year) in elem.string:
            # image tag with signed from team is right next to the joined date
            signed_from = elem.find_next("img").get("alt")
            # ignore if it's signed from the same team (e.g. different team division)
            if team in signed_from:
                continue

            # table item with the player image tag is somewhere before joined date element
            name_table = elem.find_previous_sibling("td", {"class": "posrela"})
            player = name_table.find_all("img", {"class": "bilderrahmen-fixed lazy lazy"})[0].get("alt")

            joined = elem.string

            print(f"\t{player} ({signed_from}) - {joined}")

if __name__ == "__main__":
    main()
