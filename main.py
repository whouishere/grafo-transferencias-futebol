import csv
import os
import sys
import time
from typing import Optional, Self

from bs4 import BeautifulSoup
import httpx

class StatusError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"Fonte de dados retornou erro {code}")
        self.code = code

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
        if req.status_code == 500 or req.status_code == 502 or req.status_code == 503 or req.status_code == 504:
            timeout = 5
            print(f"Erro no servidor da fonte de dados ({req.status_code}), tentando novamente em {timeout} segundos...")
            time.sleep(timeout)
            return read_from_url(url)
        raise StatusError(req.status_code)
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
    url = f"https://www.transfermarkt.com/{name_id}/kader/verein/{verein_id}/saison_id/{year}/plus/1"
    html: str

    # when in debug mode, fetch html data from cache folder
    # (in order not to send a ton of requests while just debugging)
    timeout = 10
    if not os.path.exists("samples/"):
        os.mkdir("samples")

    filepath = f"samples/{name_id}{verein_id}{year}.html"
    if not os.path.exists(filepath):
        print(f"Esperando {timeout} segundos para coletar o próximo dado...")
        time.sleep(timeout)
        try:
            html = read_from_url(url)
        except StatusError as err:
            # bail out on non-existent teams
            if err.code == 301 or err.code == 302:
                # write it anyway to avoid making the same request again in a future run
                with open(filepath, "w") as f:
                    f.write("")
                return []
            else:
                raise

        with open(filepath, "w") as f:
            f.write(html)
    else:
        html = read_from_file(filepath)

    # bail out on faulty data
    if html == "":
        return []
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

depth_iter = 0

def collect_team_tree(curr_name_id: str, curr_verein_id: int, year: int, total_depth: int):
    connections_from = parse_team(curr_name_id, curr_verein_id, year)
    for connection in connections_from:
        edges.append(TeamEdge(int(connection.verein), curr_verein_id, connection.transfers))

        global depth_iter
        if depth_iter < total_depth:
            depth_iter += 1
            collect_team_tree(connection.id, int(connection.verein), year, total_depth)
            depth_iter -= 1

def main():
    name_id: str
    verein_id: int
    year_start: int
    year_end: int
    depth: int

    if len(sys.argv) > 1:
        name_id = sys.argv[1]
        verein_id = int(sys.argv[2])
        year_start = int(sys.argv[3])
        year_end = int(sys.argv[4])
        depth = int(sys.argv[5])
    else:
        name_id = input("Time ID do transfermarkt: ")
        verein_id = int(input("Time ID serial (verein) do transfermarkt: "))
        year_start = int(input("Primeiro ano do período de transferências: "))
        year_end = int(input("Último ano do período de transferências: "))
        depth = int(input("Profundidade da coleta: "))

    for year in range(year_start, year_end + 1):
        collect_team_tree(name_id, verein_id, year, depth)

    print("\nSalvando dados...")
    filename = f"vertices_{name_id}_{year_start}{year_end}.csv"
    with open(filename, "w", newline="") as file:
        node_writer = csv.writer(file)
        node_writer.writerow(["Id", "Label"])
        for node in nodes:
            node_writer.writerow([str(node.id), node.label])
    print(f"Dados de vértices salvos em {filename}")

    filename = f"arestas_{name_id}_{year_start}{year_end}.csv"
    with open(filename, "w", newline="") as file:
        edge_writer = csv.writer(file)
        edge_writer.writerow(["Source", "Target", "Weight"])
        for edge in edges:
            edge_writer.writerow([str(edge.from_id), str(edge.to_id), str(edge.weight)])
    print(f"Dados de arestas salvos em {filename}")

if __name__ == "__main__":
    main()
