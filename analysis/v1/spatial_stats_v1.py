"""Frozen 6-neighbour spatial tests shared by M4 and M5.

Coordinates are projected metres. Join count uses the undirected union of
each point's six nearest neighbours; permutations retain the failed count.
"""
import numpy as np
from scipy.spatial import cKDTree

SEED = 20261005
N_PERM = 999


def knn6_edges(xy):
    xy = np.asarray(xy, dtype=float)
    if len(xy) < 2:
        return np.empty((0, 2), dtype=np.int64)
    k = min(6, len(xy) - 1)
    candidates = cKDTree(xy).query(xy, k=min(len(xy), k + 2))[1]
    candidates = np.asarray(candidates).reshape(len(xy), -1)
    edges = set()
    for i, neighbours in enumerate(candidates):
        chosen = [int(j) for j in neighbours if int(j) != i][:k]
        for j in chosen:
            edges.add((min(i, j), max(i, j)))
    return np.asarray(sorted(edges), dtype=np.int64).reshape(-1, 2)


def joincount_knn6(xy, failed, seed=SEED, n_perm=N_PERM):
    failed = np.asarray(failed, dtype=bool)
    edges = knn6_edges(xy)
    if len(edges) == 0:
        return {"observed": 0.0, "perm_mean": 0.0, "perm_sd": 0.0,
                "z": None, "p_perm": 1.0, "n_edges": 0,
                "n_spatial": len(failed), "n_failed_spatial": int(failed.sum())}
    observed = float((failed[edges[:, 0]] & failed[edges[:, 1]]).sum())
    rng = np.random.default_rng(seed)
    perm = np.empty(n_perm)
    for b in range(n_perm):
        labels = rng.permutation(failed)
        perm[b] = (labels[edges[:, 0]] & labels[edges[:, 1]]).sum()
    sd = float(perm.std(ddof=1))
    z = (observed - float(perm.mean())) / sd if sd > 0 else None
    return {"observed": observed, "perm_mean": float(perm.mean()),
            "perm_sd": sd, "z": z,
            "p_perm": float((1 + (perm >= observed).sum()) / (n_perm + 1)),
            "n_edges": int(len(edges)), "n_spatial": len(failed),
            "n_failed_spatial": int(failed.sum())}
