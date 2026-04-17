"""Airport map representation built from a GraphML taxiway network.

The map stores nodes (intersections / endpoints) and edges (taxiway segments)
in UTM coordinates, and exposes helpers used by planners and the simulator.
"""

import numpy as np
import random
from pyproj import Transformer
from collections import defaultdict
import networkx as nx
from opentaxi.tools import dense_polyline2d, parse_linestring, lonlat_to_utm


class AirportMap:
    """Load and manage an airport surface graph from a GraphML file.

    Attributes:
        G: NetworkX DiGraph of the airport taxiway network.
        point_dict: Mapping ``{node_id: (x, y)}`` in UTM metres.
        way_dict: Column-oriented edge attribute store.
    """

    # Manual fixes for taxiway reference IDs in the source data.
    TAXIWAY_NAME_FIXES = {
        'V11': 'V9',
        'T13': 'T12',
    }

    def __init__(self, graphml_path, utm_epsg="EPSG:32648"):
        self.graphml_path = graphml_path
        self.utm_epsg = utm_epsg
        self.transformer = Transformer.from_crs(
            "EPSG:4326", utm_epsg, always_xy=True)
        self.transformer_to_webmercator = Transformer.from_crs(
            utm_epsg, "EPSG:3857", always_xy=True)

        self.G = None
        self.point_dict = {}
        self.way_dict = {}
        self.way_idxs = defaultdict(list)
        self.edge_headings = {}

        self.node_runway = set()
        self.node_parking = set()

        self._parse_graphml()
        self._fix_taxiway_names()
        self._build_way_index()
        self._compute_edge_headings()
        self._identify_special_nodes()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_graphml(self):
        """Parse the GraphML file into nodes and edges."""
        self.G = nx.read_graphml(self.graphml_path)

        for idx, attr in self.G.nodes(data=True):
            x = float(attr["x"])
            y = float(attr["y"])
            point = lonlat_to_utm(self.transformer, [(x, y)])
            self.point_dict[int(idx)] = point[0]

        for start_idx, end_idx, attr in self.G.edges(data=True):
            if "geometry" not in attr:
                continue

            points_lonlat = parse_linestring(attr["geometry"])
            points_xy = lonlat_to_utm(self.transformer, points_lonlat)
            xs = np.array([p[0] for p in points_xy])
            ys = np.array([p[1] for p in points_xy])
            line = dense_polyline2d(np.column_stack((xs, ys)))

            self.way_dict.setdefault('id', []).append(attr.get('ref', ''))
            self.way_dict.setdefault('oneway', []).append(attr['oneway'])
            self.way_dict.setdefault('aeroway', []).append(attr['aeroway'])
            self.way_dict.setdefault('path', []).append(line)
            self.way_dict.setdefault('start_idx', []).append(start_idx)
            self.way_dict.setdefault('end_idx', []).append(end_idx)
            self.way_dict.setdefault('length', []).append(
                float(attr.get('length', 0)))
            self.way_dict.setdefault('width', []).append(
                float(attr.get('width', 0)) if 'width' in attr else 0)
            self.way_dict.setdefault('name', []).append(
                attr.get('name', ''))
            self.way_dict.setdefault('reversed', []).append(
                attr.get('reversed', 'False'))

    def _fix_taxiway_names(self):
        """Apply manual taxiway name corrections."""
        fix_count = 0
        for i, ref in enumerate(self.way_dict.get('id', [])):
            if ref in self.TAXIWAY_NAME_FIXES:
                self.way_dict['id'][i] = self.TAXIWAY_NAME_FIXES[ref]
                fix_count += 1
        if fix_count > 0:
            print(f"AirportMap: Fixed {fix_count} taxiway name(s)")

    def _build_way_index(self):
        """Build a lookup from (start, end) node pair to edge indices."""
        for i, (s, e) in enumerate(
                zip(self.way_dict["start_idx"], self.way_dict["end_idx"])):
            self.way_idxs[(s, e)].append(i)

    def _compute_edge_headings(self):
        """Compute start and end heading angles for each edge."""
        for i, path in enumerate(self.way_dict["path"]):
            if len(path) < 2:
                continue
            dx_s = path[1, 0] - path[0, 0]
            dy_s = path[1, 1] - path[0, 1]
            start_heading = np.arctan2(dy_s, dx_s)

            dx_e = path[-1, 0] - path[-2, 0]
            dy_e = path[-1, 1] - path[-2, 1]
            end_heading = np.arctan2(dy_e, dx_e)

            key = (self.way_dict["start_idx"][i],
                   self.way_dict["end_idx"][i])
            self.edge_headings[key] = (start_heading, end_heading)

    def _identify_special_nodes(self):
        """Classify nodes as runway-interior or parking dead-ends."""
        runway_u_nodes = set()
        parking_v_nodes = set()
        taxiway_v_nodes = set()
        non_parking_u_nodes = set()

        for i, aeroway in enumerate(self.way_dict["aeroway"]):
            start_idx = int(self.way_dict["start_idx"][i])
            end_idx = int(self.way_dict["end_idx"][i])

            if aeroway == "runway":
                runway_u_nodes.add(start_idx)
            else:
                taxiway_v_nodes.add(end_idx)

            if aeroway == "parking_position":
                parking_v_nodes.add(end_idx)
            else:
                non_parking_u_nodes.add(start_idx)

        self.node_runway = runway_u_nodes
        self.node_parking = parking_v_nodes
        self.valid_runway_endpoints = runway_u_nodes & taxiway_v_nodes
        self.valid_parking_startpoints = parking_v_nodes & non_parking_u_nodes

    # ------------------------------------------------------------------
    # Node queries
    # ------------------------------------------------------------------

    def get_point(self, node_idx):
        """Return (x, y) position of a node."""
        return self.point_dict[int(node_idx)]

    def get_neighbors(self, node_idx):
        """Return list of neighbour node IDs."""
        return list(self.G.neighbors(str(node_idx)))

    def get_random_endpoints(self, seed=None):
        """Return a random (parking_start, runway_end) pair."""
        if seed is None:
            seed = random.randint(0, 1000)
        rnd = random.Random(seed)

        park_idxs = [i for i, v in enumerate(self.way_dict["aeroway"])
                     if v == "parking_position"]
        runway_idxs = [i for i, v in enumerate(self.way_dict["aeroway"])
                       if v == "runway"]

        park_idx = rnd.choice(park_idxs)
        runway_idx = rnd.choice(runway_idxs)

        start_idx = self.way_dict["end_idx"][park_idx]
        end_idx = self.way_dict["start_idx"][runway_idx]
        return start_idx, end_idx

    def get_valid_runway_endpoints(self):
        """Return sorted list of valid runway endpoint node IDs."""
        return sorted(self.valid_runway_endpoints)

    def get_valid_parking_startpoints(self):
        """Return sorted list of valid parking start-point node IDs."""
        return sorted(self.valid_parking_startpoints)

    def get_excluded_nodes(self):
        """Return (runway_nodes, parking_nodes) sets for planning."""
        return self.node_runway, self.node_parking

    # ------------------------------------------------------------------
    # Edge queries
    # ------------------------------------------------------------------

    def get_edge_heading(self, from_idx, to_idx):
        """Return (start_heading, end_heading) in radians for an edge."""
        return self.edge_headings.get(
            (str(from_idx), str(to_idx)), (0, 0))

    def get_edge_length(self, from_idx, to_idx):
        """Return edge length in metres between two nodes."""
        idxs = self.way_idxs.get((str(from_idx), str(to_idx)), [])
        if not idxs:
            return float('inf')
        return self.way_dict["length"][idxs[0]]

    def get_bounds(self):
        """Return (x_min, x_max, y_min, y_max) of the map."""
        all_x, all_y = [], []
        for line in self.way_dict["path"]:
            all_x.extend(line[:, 0])
            all_y.extend(line[:, 1])
        return min(all_x), max(all_x), min(all_y), max(all_y)
