import os
import sys
from typing import Self

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

class MarktTeamConnection:
    def __init__(self, id: str, verein: str) -> None:
        """
        `id` is transfermarkt's URLs string team identifier (e.g. `santos-fc`)
        `verein` is transfermarkt's URLs integer team identifier
        in a typical team page URL, it will be formatted like this:
        `<https://www.transfermarkt.com/{id}/.../verein/{verein}/...>`
        """
        self.id = id
        self.verein = verein
        self.transfers = 1

    def find_in_list(self, b: list[Self]) -> int:
        for i, team in enumerate(b):
            if self.id == team.id and self.verein == team.verein:
                return i
        return -1

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

    connections_from: list[MarktTeamConnection] = []

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

            # just as the signed from team name, its URL is also found right next to the joined date
            signed_from_page_route = elem.find_next("a").get("href")
            route_split = signed_from_page_route.split("/")
            # route_split[1] is team id and route_split[4] is team verein
            connection = MarktTeamConnection(route_split[1], route_split[4])
            idx = connection.find_in_list(connections_from)
            if idx == -1: # not found
                connections_from.append(connection)
            else:
                connections_from[idx].transfers += 1

            # table item with the player image tag is somewhere before joined date element
            name_table = elem.find_previous_sibling("td", {"class": "posrela"})
            player = name_table.find_all("img", {"class": "bilderrahmen-fixed lazy lazy"})[0].get("alt")

            joined = elem.string

            print(f"\t{player} ({signed_from}) - {joined}")

    print(f"{len(connections_from)} transferências ao total.\n")
    for team in connections_from:
        print(f"{team.id}/{team.verein} ({team.transfers})")

if __name__ == "__main__":
    main()
