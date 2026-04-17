"""Geometric utility functions for path and coordinate operations."""

import numpy as np
import numpy.linalg as npl
import math


def wrap_angle(theta):
    """Normalize angle to [-pi, pi]."""
    return (theta + np.pi) % (2 * np.pi) - np.pi


def polyline_length(line):
    """Compute cumulative arc length along a polyline.

    Args:
        line: Nx2 array of (x, y) points.

    Returns:
        1D array of cumulative distances starting from 0.
    """
    if len(line) <= 1:
        return np.array([0.0])
    dist_list = np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))
    return np.concatenate(([0.0], dist_list))


def dense_polyline2d(line, resolution=0.1):
    """Densify a polyline by linear interpolation.

    Args:
        line: Nx2 array of (x, y) points.
        resolution: Maximum gap between consecutive points (meters).

    Returns:
        Densified Mx2 array.
    """
    if line is None or len(line) == 0:
        raise ValueError("Line input is null")

    s = np.cumsum(npl.norm(np.diff(line, axis=0), axis=1))
    s = np.concatenate([[0], s])
    num = int(round(s[-1] / resolution))

    try:
        s_space = np.linspace(0, s[-1], num=num)
    except Exception:
        raise ValueError(num, s[-1], len(s))

    x = np.interp(s_space, s, line[:, 0])
    y = np.interp(s_space, s, line[:, 1])
    return np.array([x, y]).T


def cartesian_to_frenet(x, y, line):
    """Convert Cartesian coordinates to Frenet frame (s, d).

    Args:
        x, y: Query point coordinates.
        line: Reference polyline as Nx2 array.

    Returns:
        (s, d): Arc length and lateral offset.
    """
    if len(line) < 2:
        raise ValueError("Reference line must have at least 2 points.")

    dist_line = npl.norm(line - [x, y], axis=1)
    closest_idx = np.argmin(dist_line)
    dist_list = np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))
    dist_list = np.concatenate([[0], dist_list])

    dist_s = round(dist_list[closest_idx], 1)
    dist_d = round(math.sqrt((x - line[closest_idx][0])**2 +
                              (y - line[closest_idx][1])**2), 1)

    tang = np.diff(line, axis=0)
    tang = np.vstack((tang, tang[-1]))
    c_prod = np.cross(tang[closest_idx], np.array([x, y]) - line[closest_idx])
    if c_prod < 0:
        dist_d = -dist_d

    return dist_s, dist_d


def find_waypoint_in_curve(curr_s, path_s, ref_path):
    """Find the (x, y) position on a reference path at arc length *curr_s*.

    Args:
        curr_s: Target arc length.
        path_s: Cumulative arc length array of *ref_path*.
        ref_path: Nx2 array of waypoints.

    Returns:
        (x, y) tuple.
    """
    if ref_path is None or len(ref_path) < 2:
        raise ValueError("Reference path must have at least 2 points.")
    idx = np.argmin(np.abs(path_s - curr_s))
    return (ref_path[idx, 0], ref_path[idx, 1])


def parse_linestring(wkt):
    """Parse a WKT LINESTRING into a list of (lon, lat) tuples."""
    coords_text = wkt.replace("LINESTRING", "").strip(" ()")
    points = []
    for p in coords_text.split(","):
        lon, lat = map(float, p.split())
        points.append((lon, lat))
    return points


def lonlat_to_utm(transformer, points_lonlat):
    """Convert lon/lat coordinates to UTM using a pyproj Transformer.

    Args:
        transformer: pyproj.Transformer instance.
        points_lonlat: List of (lon, lat) tuples.

    Returns:
        List of (x, y) tuples in meters.
    """
    xs, ys = transformer.transform(
        [p[0] for p in points_lonlat],
        [p[1] for p in points_lonlat]
    )
    return list(zip(xs, ys))


def lonlat_to_webmercator(transformer, points_lonlat):
    """Convert lon/lat coordinates to Web Mercator projection.

    Args:
        transformer: pyproj.Transformer instance (to EPSG:3857).
        points_lonlat: List of (lon, lat) tuples.

    Returns:
        List of (x, y) tuples.
    """
    result = []
    for lon, lat in points_lonlat:
        x, y = transformer.transform(lon, lat)
        result.append((x, y))
    return result


def pointtilt(x, y, line):
    """Compute the tangent angle at the closest point on a polyline.

    Args:
        x, y: Query point coordinates.
        line: Reference polyline as Nx2 array.

    Returns:
        Tangent angle in radians.
    """
    if len(line) < 2:
        raise ValueError("Reference line must have at least 2 points.")
    dist_line = npl.norm(line - [x, y], axis=1)
    closest_idx = np.argmin(dist_line)
    diff_list = np.diff(line, axis=0)
    diff_list = np.vstack((diff_list[0, :], diff_list))
    return np.arctan2(diff_list[closest_idx][1], diff_list[closest_idx][0])


def pointcurvature(x, y):
    """Compute curvature from three points.

    Args:
        x: Array of three x-coordinates.
        y: Array of three y-coordinates.

    Returns:
        (kappa, normal): Curvature value and unit normal vector.
    """
    t_a = npl.norm([x[1] - x[0], y[1] - y[0]])
    t_b = npl.norm([x[2] - x[1], y[2] - y[1]])

    M = np.array([
        [1, -t_a, t_a**2],
        [1,  0,   0     ],
        [1,  t_b, t_b**2]
    ])

    a = np.matmul(npl.inv(M), x)
    b = np.matmul(npl.inv(M), y)

    kappa = 2 * (a[2] * b[1] - b[2] * a[1]) / (a[1]**2. + b[1]**2.)**(1.5)
    return kappa, [b[1], -a[1]] / np.sqrt(a[1]**2. + b[1]**2.)


def linecurvature(line):
    """Compute curvature along a polyline.

    Args:
        line: Nx2 array of (x, y) points.

    Returns:
        1D array of curvature values (length N).
    """
    ka = [0]
    for idx in range(len(line) - 2):
        x = np.array([line[idx][0], line[idx + 1][0], line[idx + 2][0]])
        y = np.array([line[idx][1], line[idx + 1][1], line[idx + 2][1]])
        kappa, _ = pointcurvature(x, y)
        ka.append(kappa)
    ka.append(ka[-1])
    return np.array(ka)
