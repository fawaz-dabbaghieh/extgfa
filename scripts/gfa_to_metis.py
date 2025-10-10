#!/usr/bin/env python3
"""
Convert GFA (v1 or v2) to METIS (.graph) format using disk-backed node ID mapping and external sort.
Also validates the GFA input to some extent (warnings for invalid lines or repeated lines).
Produces an undirected simple graph (no self-loops).
Requires Unix 'sort' command (GNU or BSD coreutils).
Memory-efficient, can handle very large graphs.

Notes from your TODOs in the JSON:
- shelve was tried and found slower than sqlite3 (left in comments)
- in-memory dict path could be added later for small graphs
"""

import argparse
import gzip
import os
import shutil
import sqlite3
import subprocess
import sys
import time


def open_gfa(path, mode="rt"):
    if path.endswith(".gz"):
        return gzip.open(path, mode)
    return open(path, mode, encoding="utf-8")


def run_sort(input_path, output_path, tmpdir=None, mem="50%", unique=True, threads=1):
    """Run external 'sort' command to sort a 2-column whitespace-separated file numerically by both columns."""
    if threads < 1:
        threads = 1
    elif threads > (os.cpu_count() or 1):
        threads = os.cpu_count() or 1

    cmd = ["sort", "-n", "--parallel", str(threads), "-k1,1", "-k2,2"]  # first key then second key, numeric
    if unique:
        cmd.append("-u")
    if tmpdir:
        cmd.extend(["-T", tmpdir])
    if mem:
        cmd.extend(["-S", mem])

    # Force C locale for speed and stable behavior
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    with open(input_path, "rb") as fin, open(output_path, "wb") as fout:
        subprocess.run(cmd, stdin=fin, stdout=fout, check=True, env=env)


def count_edges(input_path):
    """Count lines in a file (number of arcs in the file)."""
    result = subprocess.run(["wc", "-l", input_path], check=True, capture_output=True, text=True)
    return int(result.stdout.split()[0])


def count_edges_streaming(input_path):
    c = 0
    with open(input_path, "r", encoding="utf-8") as f:
        for _ in f:
            c += 1
    return c


def ensure_sort_exists():
    """Check that 'sort' is available on PATH."""
    if not shutil.which("sort"):
        sys.stderr.write("ERROR: 'sort' not found on PATH. Install coreutils/bsd sort.\n")
        sys.exit(1)


# ---------- SQLite node-id mapping (on-disk) ----------

def init_node_db(db_path):
    """Initialize SQLite DB for node name -> integer ID mapping. Returns connection."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Performance pragmas
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=OFF;")
    cur.execute("PRAGMA temp_store=MEMORY;")
    cur.execute("PRAGMA cache_size=-200000;")  # ~200 MB cache
    cur.execute("PRAGMA mmap_size=-20000;")

    # id autoincrements; name unique
    cur.execute("""
                CREATE TABLE IF NOT EXISTS nodes(
                                                    id   INTEGER PRIMARY KEY AUTOINCREMENT,
                                                    name TEXT UNIQUE
                );
                """)
    conn.commit()
    return conn


def get_or_create_id(cur, name):
    """Get or create integer node ID for given name. Returns integer ID."""
    row = cur.execute("SELECT id FROM nodes WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    try:
        cur.execute("INSERT INTO nodes(name) VALUES (?)", (name,))
        # No explicit commit required for visibility in same connection/cursor
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return cur.execute("SELECT id FROM nodes WHERE name=?", (name,)).fetchone()[0]


def gfa_to_metis_external(
        gfa_path,
        out_graph_path,
        tmpdir="./tmp",
        sort_mem="50%",
        keep_tmp=False,
        progress_every=0,
        save_node_order=None,
        threads=1,
):
    """
    Convert GFA -> METIS (.graph) using disk-backed mapping + external sort.
    Produces an undirected simple graph (no self-loops, no multiedges).
    """
    ensure_sort_exists()  # make sure that 'sort' is available on PATH
    # Prepare working directory
    if os.path.exists(tmpdir):
        print(f"{tmpdir} already exists, removing it first")
        shutil.rmtree(tmpdir, ignore_errors=True)
        work = tmpdir
    else:
        work = tmpdir
    os.makedirs(work, exist_ok=True)
    print(f"Working directory: {work}")

    db_path = os.path.join(work, "nodes.sqlite")
    edges_unsorted = os.path.join(work, "edges.unsorted")
    edges_sorted = os.path.join(work, "edges.sorted")

    # SQLite mapping
    sql_connection = init_node_db(db_path)
    sql_cursor = sql_connection.cursor()

    # Parse GFA, assign IDs on disk, write arcs "u v" (both directions) for undirected edges
    total_lines = 0
    total_edges_raw = 0
    to_ignore = {"#", "H", "\n", "\r"}
    start_time = time.perf_counter()
    print(f"[Step 1]: Parsing GFA, assigning node IDs, writing edges...")

    with open_gfa(gfa_path, "rt") as in_gfa, open(edges_unsorted, "w", encoding="utf-8") as edges_out:
        for line in in_gfa:
            total_lines += 1
            if not line or line[0] in to_ignore:
                continue
            parts = line.rstrip().split("\t")
            if parts[0] == "S":
                # segment
                if len(parts) >= 2:
                    get_or_create_id(sql_cursor, parts[1])
                else:
                    print(
                        f"WARNING: invalid S line (too few fields) at line {total_lines}: {line.strip()}. Skipping!",
                        file=sys.stderr,
                    )

            elif parts[0] == "L":
                # GFA1: L from from_orient to to_orient overlap ...
                if len(parts) >= 4:
                    u_name = parts[1]
                    v_name = parts[3]
                    u = get_or_create_id(sql_cursor, u_name)
                    v = get_or_create_id(sql_cursor, v_name)
                    if u != v:  # drop self-loops
                        edges_out.write(f"{u} {v}\n")
                        edges_out.write(f"{v} {u}\n")
                        total_edges_raw += 1
                else:
                    print(
                        f"WARNING: invalid L line (too few fields) at line {total_lines}: {line.strip()}. Skipping!",
                        file=sys.stderr,
                    )

            elif parts[0] == "E":
                # GFA2: E <eid> <sid1> <sid2> ...
                if len(parts) >= 4:
                    u = get_or_create_id(sql_cursor, parts[2])
                    v = get_or_create_id(sql_cursor, parts[3])
                    if u != v:
                        edges_out.write(f"{u} {v}\n")
                        edges_out.write(f"{v} {u}\n")
                        total_edges_raw += 1
                else:
                    print(
                        f"WARNING: invalid E line (too few fields) at line {total_lines}: {line.strip()}. Skipping!",
                        file=sys.stderr,
                    )

            # else ignore other record types: P/W/F/G/...

            if progress_every and (total_lines % progress_every == 0):
                n = sql_cursor.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
                print(f"[Step 1] lines={total_lines:,} nodes≈{n:,} raw_edges≈{total_edges_raw:,}")

    print(f"Finished parsing GFA in {time.perf_counter() - start_time:.2f}s.")
    print(f"Counting nodes...")
    n_nodes = sql_cursor.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    print(f"Number of nodes: {n_nodes}")

    # Optional: write node map (name \t id)
    if save_node_order:
        print(f"Writing node map to: {save_node_order}")
        with open(save_node_order, "w", encoding="utf-8") as mout:
            for row in sql_cursor.execute("SELECT name, id FROM nodes ORDER BY id"):
                # row[0]=name, row[1]=id
                mout.write(f"{row[0]}\n")

    # Phase 2: sort+unique arcs; because we wrote both directions already,
    # 'edges_sorted' will be (u->v) arcs without duplicates, sorted by (u,v).
    print(f"[Step 2]: Sorting and deduplicating edges...")
    start_time = time.perf_counter()
    run_sort(edges_unsorted, edges_sorted, tmpdir=work, mem=sort_mem, unique=True, threads=threads)
    print(f"Finished sorting and deduplicating in {time.perf_counter() - start_time:.2f}s.")

    # Count unique undirected edges: each undirected edge appears twice in 'edges_sorted'
    print(f"Counting unique edges...")
    start_time = time.perf_counter()
    n_edges = int(count_edges(edges_sorted) / 2)
    print(f"Number of edges: {n_edges}. Counted in {time.perf_counter() - start_time:.2f}s.")

    # Phase 3: stream arcs -> adjacency lines, write METIS file
    start_time = time.perf_counter()
    with open(edges_sorted, "r", encoding="utf-8") as in_edges, open(out_graph_path, "w", encoding="utf-8") as out_metis:
        print("[Step 3] Writing METIS adjacency...")
        out_metis.write(f"{n_nodes} {n_edges}\n")
        current_u = 1
        neighbors = []

        for line in in_edges:
            s = line.strip()
            if not s:
                continue
            u_str, v_str = s.split()
            u = int(u_str)
            v = int(v_str)

            # Fill empty nodes up to u
            while current_u < u:
                out_metis.write((" ".join(map(str, neighbors)) + "\n") if neighbors else "\n")
                neighbors.clear()
                current_u += 1

            if u != current_u:
                # Write previous node line
                out_metis.write((" ".join(map(str, neighbors)) + "\n") if neighbors else "\n")
                current_u = u
                neighbors = []

            # neighbors are already sorted and deduped by (u,v)
            neighbors.append(v)

        # flush last collected node
        if neighbors:
            out_metis.write(" ".join(map(str, neighbors)) + "\n")
            neighbors.clear()

        # flush any remaining empty nodes up to n_nodes
        while current_u <= n_nodes:
            out_metis.write("\n")
            current_u += 1

    # Cleanup
    if not keep_tmp:
        print("removing tmp files")
        try:
            sql_connection.close()
            shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass

    print(f"Finished writing METIS in {time.perf_counter() - start_time:.2f}s.")
    print(f"Nodes (n_nodes): {n_nodes}")
    print(f"Unique undirected edges (n_uniq_edges): {n_edges}")
    print(f"METIS written to: {out_graph_path}")


# ---------- CLI ----------

def main():
    argpars = argparse.ArgumentParser(
        description="External-sort GFA -> METIS (.graph). Undirected, deduped, memory-light."
    )
    argpars.add_argument("gfa", help="Input .gfa (optionally .gz)")
    argpars.add_argument("out", help="Output METIS .graph path")
    argpars.add_argument("--tmpdir", default="./tmp",
                         help="Working directory for big temp files (recommended: fast disk), default='./tmp'")
    argpars.add_argument("--sort-mem", default="50%",
                         help="Memory limit for 'sort' (e.g. 50%%, 8G). Default: 50%%")
    argpars.add_argument("--keep-tmp", action="store_true", help="Keep intermediate files (debug)")
    argpars.add_argument("--progress-every", type=int, default=0, help="Print progress every N lines")
    argpars.add_argument("--save-node-order", help="Write a TSV mapping: <name>\\t<id>")
    argpars.add_argument("--threads", type=int, default=1, help="Number of threads for the sorting step")
    args = argpars.parse_args()

    gfa_to_metis_external(
        args.gfa,
        args.out,
        tmpdir=args.tmpdir,
        sort_mem=args.sort_mem,
        keep_tmp=args.keep_tmp,
        progress_every=args.progress_every,
        save_node_order=args.save_node_order,
        threads=args.threads
    )


if __name__ == "__main__":
    main()
