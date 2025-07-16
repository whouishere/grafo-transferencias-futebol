import os
import sys
import time
from typing import Optional, Self

from bs4 import BeautifulSoup
import httpx

def read_from_file(filename: str) -> str:
    with open(filename) as f:
        return f.read()

def read_from_url(url: str) -> str:
    print(f"Baixando dados de {url}...")

    try:
        req = httpx.request("GET", url, timeout=60.0)
    except httpx.ReadTimeout:
        raise RuntimeError("Timeout de download dos dados")

    if req.status_code != 200:
        raise RuntimeError(f"Fonte de dados retornou erro {req.status_code}")
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

    def find_in_list(self, b: list[Self]) -> Optional[int]:
        for i, team in enumerate(b):
            if self.id == team.id and self.verein == team.verein:
                return i
        return None

class TeamNode:
    def __init__(self, id: int, label: str) -> None:
        self.id = id
        self.label = label

    def is_in_list(self, b: list[Self]) -> bool:
        for node in b:
            if self.id == node.id:
                return True
        return False

class TeamEdge:
    def __init__(self, from_id: int, to_id: int, weight: int) -> None:
        self.from_id = from_id
        self.to_id = to_id
        self.weight = weight

nodes: list[TeamNode] = []
edges: list[TeamEdge] = []

def parse_team(name_id: str, verein_id: int, year: int) -> list[MarktTeamConnection]:
    url = f"https://www.transfermarkt.com/{name_id}/kader/verein/{verein_id}/saison_id/{year-1}/plus/1"
    html: str

    # when in debug mode, fetch html data from cache folder
    # (in order not to send a ton of requests while just debugging)
    timeout = 10
    if "debug" in sys.argv[1]:
        if not os.path.exists("samples/"):
            os.mkdir("samples")

        filepath = f"samples/{name_id}{verein_id}{year}.html"
        if not os.path.exists(filepath):
            print(f"Esperando {timeout} segundos para coletar o próximo dado...")
            time.sleep(timeout)
            html = read_from_url(url)
            with open(filepath, "w") as f:
                f.write(html)
        else:
            html = read_from_file(filepath)
    else:
        print(f"Esperando {timeout} segundos para coletar o próximo dado...")
        time.sleep(timeout)
        html = read_from_url(url)

    soup = BeautifulSoup(html, "html.parser")
    team = soup.find("header", {"class": "data-header"}).find("h1", {"class": "data-header__headline-wrapper"}).string.strip()

    new_node = TeamNode(int(verein_id), team)
    if not new_node.is_in_list(nodes):
        nodes.append(new_node)

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
            if idx == None: # not found
                connections_from.append(connection)
            else:
                connections_from[idx].transfers += 1

            new_node = TeamNode(int(connection.verein), signed_from)
            if not new_node.is_in_list(nodes):
                nodes.append(new_node)

    return connections_from

def main():
    print("--- DEBUG MODE ---")
    name_id = input("Time ID do transfermarkt: ")
    verein_id = int(input("Time ID serial (verein) do transfermarkt: "))
    year = int(input("Ano de transferências: "))

    connections_from = parse_team(name_id, verein_id, year)
    for connection in connections_from:
        edges.append(TeamEdge(int(connection.verein), verein_id, connection.transfers))

        new_connections = parse_team(connection.id, int(connection.verein), year)
        for new_connection in new_connections:
            edges.append(TeamEdge(int(new_connection.verein), int(connection.verein), new_connection.transfers))

    print("\nVértices:")
    for node in nodes:
        print(f"\t{node.id} - {node.label}")

    print("\nArestas:")
    for edge in edges:
        from_team = ""
        to_team = ""
        for node in nodes:
            if edge.from_id == node.id:
                from_team = node.label
            if edge.to_id == node.id:
                to_team = node.label
        print(f"\t{from_team} -> {to_team} ({edge.weight})")

if __name__ == "__main__":
    main()
