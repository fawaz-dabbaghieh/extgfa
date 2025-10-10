// Minimal GFA1 (S/L) loader that builds a bidirected handle graph in CSR form.
// - Ignores P lines (paths) and tags for now.
// - Supports links that reference segments defined later.
// - Stores each node's DNA sequence packed 2-bits/base **inside the Node**.


// Public API exposed at the bottom for basic traversal + sequence decode.

#include <string>
#include <vector>
#include <unordered_map>
#include <fstream>
#include <ctime>
#include <iostream>
#include <sstream>
#include <cassert>
#include <algorithm>


// ------------- Handles
using nid_t    = uint32_t;          // index into nodes[]
using len_t    = uint32_t;          // length of a sequence
using idx_t    = uint32_t;          // offsets into arenas / arrays (avoid clash with POSIX off_t)
using handle_t = uint64_t;          // [node location | orientation (0)]

inline handle_t make_handle(const nid_t n, const bool rev) { return (static_cast<uint64_t>(n) << 1) | (rev ? 1ULL : 0ULL); }
inline nid_t    id_of(const handle_t h)  { return static_cast<nid_t>(h >> 1); }
inline bool     is_rev(const handle_t h) { return (h & 1ULL) != 0ULL; }
inline handle_t flip(const handle_t h)   { return h ^ 1ULL; }

static constexpr char LUT[4] = {'A','C','G','T'};

// ---------- base enc/dec helpers ----------
inline char dec_base(const uint8_t v) {return LUT[v & 3]; }

inline uint8_t enc_base(const char c) {
    switch (c) {
        case 'A': case 'a': return 0; // 00
        case 'C': case 'c': return 1; // 01
        case 'G': case 'g': return 2; // 10
        case 'T': case 't': return 3; // 11
        default: return 0;            // map N/others to A (00). need to improve this later or only accept ACTG
    }
}

// ------------- Nodes (each owns its packed sequence)
struct Node {
    std::vector<uint64_t> seq_words; // packed 2-bit bases, little-endian per word
    std::string name;
    len_t  seq_len = 0;              // length in bases
    idx_t  arc_off_f = 0;            // start in arcs[] for forward orientation
    idx_t  arc_deg_f = 0;            // count
    idx_t  arc_off_r = 0;            // start in arcs[] for reverse orientation
    idx_t  arc_deg_r = 0;            // count
};

// ------------- Arcs (neighbors are handles)
struct Arc {
    handle_t to = 0;      // neighbor handle
    uint32_t edge_id = 0; // reserved; not used yet
    // still need to handle tags somehow, probably a vector of tag structs that have 3 members
    // tag id, type, and value, can just keep them as strings for ease of use
};

struct Graph {
    std::vector<Node> nodes;
    std::vector<Arc>  arcs;        // CSR neighbor list for both orientations

    // mapping segment name/id -> node index
    std::unordered_map<std::string, nid_t> id2idx;
};

inline std::string name_of(const handle_t h, Graph* g) {return g->nodes[static_cast<nid_t>(h >> 1)].name;}


// ---------- sequence pack/unpack on a per-Node basis ----------
static inline void node_pack_sequence_2bit(Node& n, const std::string& s) {
    n.seq_len = static_cast<len_t>(s.size());
    // we need 2*seq_len of bits as each character is 2 bits
    const uint64_t total_bits = 2 * n.seq_len;
    // allocate enough words to hold the sequence
    // 63 to ensure that if there's any reminder when dividing, it bumps to the next integer
    const size_t words = (total_bits + 63) / 64;
    n.seq_words.assign(words, 0ULL);
    uint8_t bit_pos = 0;   // next bit position
    size_t word_idx = 0;
    for (const char c : s) {
        const uint64_t v = enc_base(c);
        // v & 3ULL masks v to its lowest two bits
        // then shift that 2-bit value left to the target bit position
        // |= sets those bits in the current word without touching the rest.
        n.seq_words[word_idx] |= (v & 0x3ULL) << bit_pos;
        bit_pos += 2;
        if (bit_pos == 64) {
            bit_pos = 0; ++word_idx;
        }
    }
}

// gets the base at a certain location, returns
static inline char node_get_base2(const Node* n, const uint64_t base_index) {
    assert((void("base_index out of range"), base_index < n->seq_len));
    const uint64_t bit = base_index * 2ULL;
    const size_t wordidx = bit / 64ULL;
    const uint32_t shift = bit % 64ULL;
    const uint64_t w = n->seq_words[wordidx];
    return LUT[(w >> shift) & 0x3ULL];
}


static inline std::string node_sequence(const Node* n, bool reverse = false) {
    std::string node_seq;
    node_seq.resize(n->seq_len);
    uint64_t out_i = 0;
    for (size_t w = 0; w < n->seq_words.size(); ++w) {
        uint64_t word;
        if (reverse) {
            // flip the bits
            word = ~n->seq_words[w];
        } else {
            word = n->seq_words[w];
        }
        // up to 32 bases per full word; clamp for the final partial word
        const uint64_t remaining = n->seq_len - out_i;
        const uint64_t take = remaining < 32 ? remaining : 32;
        for (uint64_t k = 0; k < take; ++k) {
            node_seq[out_i++] = LUT[word & 0x3ULL];
            word >>= 2; // move to next base in this word
        }
    }
    if (reverse) {
        std::reverse(node_seq.begin(), node_seq.end());
        return node_seq;
    }
    return node_seq;
}

// ---------- parsing utilities ----------
static inline void rstrip(std::string& s) {
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
}

static inline std::vector<std::string> split_tab(const std::string& line) {
    std::vector<std::string> tokens;
    size_t prev_pos = 0;
    size_t current_pos = line.find('\t'); // Find the first tab

    while (current_pos != std::string::npos) {
        tokens.push_back(line.substr(prev_pos, current_pos - prev_pos));
        prev_pos = current_pos + 1; // Move past the tab
        current_pos = line.find('\t', prev_pos); // Find the next tab
    }

    // Add the last token (or the whole string if no tabs were found)
    tokens.push_back(line.substr(prev_pos));
    return tokens;
}

static bool node_exists(const std::string& name, const std::unordered_map<std::string, nid_t>& id2idx) {
    return id2idx.find(name) != id2idx.end();
}

// add a segment to the graph
static void add_node(std::vector<Node>& nodes, std::unordered_map<std::string, nid_t>& id2idx,
    const std::string& seq, const std::string& name, size_t seqlen) {

    auto id = static_cast<nid_t>(nodes.size());
    nodes.emplace_back();
    id2idx.emplace(name, id);
    Node& n = nodes[id];
    n.name = name;
    n.seq_len = seqlen;
    if (!seq.empty()) {
        node_pack_sequence_2bit(n, seq);
    } else {
        n.seq_len = 0;
        n.seq_words.clear();
    }
    // return id;
}

static nid_t get_node_id(const std::string& name, const std::unordered_map<std::string, nid_t>& id2idx) {
    auto it = id2idx.find(name);
    if (it == id2idx.end()) {
        std::cerr << "node " << name << " not found\n";
        return -1;
    }
    return it->second;
}

// ---------- GFA1 S/L loader ----------
struct PendingArc { handle_t from; handle_t to; };

// Parse an S-line in-place: get <name> and sequence length only.
// line is like: "S\t<name>\t<seq>\t<tag1>\t..."
inline bool parse_s_line(const std::string& line,
                                 std::string_view& name_out,
                                 uint32_t& len_out) {

    size_t i = 2; // after "S\t"
    size_t t1 = line.find('\t', i);
    if (t1 == std::string::npos) return false; // no <name>
    name_out = std::string_view(line.data() + i, t1 - i);

    size_t t2 = t1 + 1;                 // start of <seq>
    size_t t3 = line.find('\t', t2);    // end of <seq> or npos
    size_t end = (t3 == std::string::npos ? line.size() : t3);

    // strip trailing CR if present on the line
    if (end && line[end-1] == '\r') --end;

    if (t2 < end) len_out = static_cast<uint32_t>(end - t2);
    else len_out = 0; // '*' case or empty
    return true;
}


// Parse a GFA1 stream, consuming only S and L records. Returns true on success.
bool load_gfa1_s(const std::string& in_gfa_file, Graph& g, const bool low_mem=true) {
    std::ifstream in(in_gfa_file);
    if (!in) { std::cerr << "cannot open: " << in_gfa_file << "\n"; return false; }
    std::string line;
    int lineno = 0;

    while (std::getline(in, line)) {
        ++lineno;
        rstrip(line);
        if (line.empty()) continue;
        const char record_type = line[0];
        // first pass only looking at S records
        if (record_type != 'S') continue;

        auto record = split_tab(line);

        if (record[0].size() != 1) {
            std::cerr << "malformed record ID at line " << lineno << ": \n" << line << ", skipping\n";
            continue;
        }

        if (record.size() < 3) {
            std::cerr << "The S record has less than 3 columns at " << lineno << ": " << line << "\n";
            return false;
        }
        const std::string& name = record[1];

        if (node_exists(name, g.id2idx)) {
            std::cerr << "Duplicate S for segment '" << name << "' at line " << lineno << " skipping!";
            continue;
        }
        std::string seq;
        if (!low_mem) {
            seq  = record[2];
        }
        size_t seqlen = seq.size();
        add_node(g.nodes, g.id2idx, seq, name, seqlen);
    }
    return true;
}

bool load_gfa1_l(const std::string& in_gfa_file, Graph& g) {
    std::ifstream in(in_gfa_file);
    if (!in) { std::cerr << "cannot open: " << in_gfa_file << "\n"; return false; }
    std::string line;
    size_t lineno = 0;
    std::vector<PendingArc> pending;
    pending.reserve(1<<20); // start with some space

    while (std::getline(in, line)) {
        ++lineno;
        rstrip(line);

        if (line.empty()) continue;
        const char record_type = line[0];
        if (record_type != 'L') continue;
        auto record = split_tab(line);

        // L \t from \t from_orient \t to \t to_orient \t overlap [\t tags]
        if (record.size() < 6) {
            std::cerr << "malformed line at line " << lineno << ": " << line << " skipping\n";
            continue;
        }
        // from node id, from direction, to node id, to direction
        const std::string& from_id  = record[1];
        const std::string& from_dir = record[2];
        const std::string& to_id    = record[3];
        const std::string& to_dir   = record[4];
        if ((from_dir[0] != '+' && from_dir[0] != '-') || (to_dir[0] != '+' && to_dir[0] != '-')) {
            std::cerr << "malformed line at line " << lineno << ": " << line << " skipping\n";
            continue;
        }
        nid_t u = get_node_id(from_id, g.id2idx);
        nid_t v = get_node_id(to_id, g.id2idx);
        if (u == -1 || v == -1) {
            std::cerr << "Edge at line " << lineno << " has nodes that have no S records, skipping\n";
            continue;
        }

        handle_t hu = make_handle(u, from_dir[0] == '-');
        handle_t hv = make_handle(v, to_dir[0] == '-');
        // Add two traversal arcs: u->v and flip(v)->flip(u)
        pending.push_back({hu, hv});
        pending.push_back({flip(hv), flip(hu)});
    }
    // Second pass: build CSR
    const size_t N = g.nodes.size();
    if (N == 0) return true; // empty graph ok

    // degree per oriented node (size 2*N)
    std::vector<uint32_t> deg(2*N, 0);
    for (const auto& a : pending) {
        size_t idx = (static_cast<size_t>(id_of(a.from)) << 1) | (is_rev(a.from) ? 1 : 0);
        deg[idx]++;
    }

    // prefix sums -> offsets per oriented node
    std::vector<uint32_t> off(2*N, 0);
    uint64_t total = 0;
    for (size_t i = 0; i < 2*N; ++i) {
        off[i] = static_cast<uint32_t>(total);
        total += deg[i];
    }

    g.arcs.assign(total, {});
    std::vector<uint32_t> cur = off; // current write positions

    // scatter arcs
    for (const auto& a : pending) {
        size_t idx = (size_t(id_of(a.from)) << 1) | (is_rev(a.from) ? 1 : 0);
        uint32_t pos = cur[idx]++;
        g.arcs[pos].to = a.to;
    }

    // write Node arc offsets/degrees
    for (nid_t n = 0; n < N; ++n) {
        Node& node = g.nodes[n];
        uint32_t iF = (uint32_t(n) << 1) | 0;
        uint32_t iR = (uint32_t(n) << 1) | 1;
        node.arc_off_f = off[iF];
        node.arc_deg_f = deg[iF];
        node.arc_off_r = off[iR];
        node.arc_deg_r = deg[iR];
    }

    return true;
}

bool load_gfa1_SL(std::istream& in, Graph& g, std::string* err = nullptr) {
    std::string line;
    std::vector<PendingArc> pending;
    pending.reserve(1<<20); // start with some space

    // First pass: read S/L lines, build nodes and collect arcs
    size_t lineno = 0;
    while (std::getline(in, line)) {
        ++lineno;
        rstrip(line);
        if (line.empty()) continue;
        const char record_type = line[0];
        if (record_type == '#') continue; // comment
        if (record_type != 'S' && record_type != 'L' && record_type != 'H') continue; // ignore others now; keep H just in case
        auto record = split_tab(line);

        if (record[0].size() != 1) {
            std::cerr << "malformed record ID at line " << lineno << ": \n" << line << ", skipping\n";
            continue;
        }

        if (record_type == 'S') {
            if (record.size() < 3) {
                std::cerr << "The S record has less than 3 columns at " << lineno << ": " << line << "\n";
                assert(false);
            }
            const std::string& name = record[1];
            const std::string& seq  = record[2];
            if (node_exists(name, g.id2idx)) {
                std::cerr << "Duplicate S for segment '" << name << "' at line " << lineno << " skipping!";
                continue;
            }
            size_t seqlen = seq.size();
            add_node(g.nodes, g.id2idx, seq, name, seqlen);

        } else if (record_type == 'L') {
            // L \t from \t from_orient \t to \t to_orient \t overlap [\t tags]
            if (record.size() < 6) { if (err) *err = "Malformed L at line " + std::to_string(lineno); return false; }
            // from node id, from direction, to node id, to direction
            const std::string& from_id = record[1];
            const std::string& from_dir   = record[2];
            const std::string& to_id   = record[3];
            const std::string& to_dir  = record[4];
            if ((from_dir[0] != '+' && from_dir[0] != '-') || (to_dir[0] != '+' && to_dir[0] != '-')) {
                if (err) *err = "Bad orientations at line " + std::to_string(lineno); return false;
            }
            nid_t u = get_node_id(from_id, g.id2idx);
            nid_t v = get_node_id(to_id, g.id2idx);
            if (u == -1 || v == -1) {
                std::cerr << "Edge at line " << lineno << " has nodes that have no S records, skipping\n";
                continue;
            }
            // TODO check the handles and edges situation
            handle_t hu = make_handle(u, from_dir[0] == '-');
            handle_t hv = make_handle(v, to_dir[0] == '-');
            // Add two traversal arcs: u->v and flip(v)->flip(u)
            pending.push_back({hu, hv});
            pending.push_back({flip(hv), flip(hu)});
        }
    }

    // Second pass: build CSR
    const size_t N = g.nodes.size();
    if (N == 0) return true; // empty graph ok

    // degree per oriented node (size 2*N)
    std::vector<uint32_t> deg(2*N, 0);
    for (const auto& a : pending) {
        size_t idx = (size_t(id_of(a.from)) << 1) | (is_rev(a.from) ? 1 : 0);
        deg[idx]++;
    }

    // prefix sums -> offsets per oriented node
    std::vector<uint32_t> off(2*N, 0);
    uint64_t total = 0;
    for (size_t i = 0; i < 2*N; ++i) {
        off[i] = static_cast<uint32_t>(total);
        total += deg[i];
    }

    g.arcs.assign(total, {});
    std::vector<uint32_t> cur = off; // current write positions

    // scatter arcs
    for (const auto& a : pending) {
        size_t idx = (size_t(id_of(a.from)) << 1) | (is_rev(a.from) ? 1 : 0);
        uint32_t pos = cur[idx]++;
        g.arcs[pos].to = a.to;
    }

    // write Node arc offsets/degrees
    for (nid_t n = 0; n < N; ++n) {
        Node& node = g.nodes[n];
        uint32_t iF = (uint32_t(n) << 1) | 0;
        uint32_t iR = (uint32_t(n) << 1) | 1;
        node.arc_off_f = off[iF];
        node.arc_deg_f = deg[iF];
        node.arc_off_r = off[iR];
        node.arc_deg_r = deg[iR];
    }

    return true;
}

// ----------- Minimal traversal helpers -----------

template <class Fn>
void for_each_neighbor(const Graph& g, handle_t h, Fn&& fn) {
    const Node& n = g.nodes[id_of(h)];
    idx_t off = is_rev(h) ? n.arc_off_r : n.arc_off_f;
    idx_t deg = is_rev(h) ? n.arc_deg_r : n.arc_deg_f;
    const Arc* a = g.arcs.data() + off;
    for (idx_t i = 0; i < deg; ++i) fn(a[i].to);
}


int main(int argc, char** argv) {
    if (argc < 3) { std::cerr << "usage: " << argv[0] << " file.gfa test_node_id\n"; return 1; }
    std::string gfa_file = argv[1];
    std::string test_node = argv[2];
    // todo need to check if gfa_file exists
    // std::ifstream in(argv[1]);
    // if (!in) { std::cerr << "cannot open: " << argv[1] << "\n"; return 1; }

    Graph g;
    std::string err;

    time_t current_time = time(NULL);
    char* time_string = ctime(&current_time);
    std::cout << time_string << std::endl;
    std::cout << "Loading GFA1 file's nodes " << gfa_file << std::endl;
    if (!load_gfa1_s(gfa_file, g, true)) {
        std:: cerr << "Error loading gfa1 file's nodes " << gfa_file << "\n";
        return 1;
    }

    current_time = time(NULL);
    time_string = ctime(&current_time);
    std::cout << time_string << std::endl;
    std::cout << "finished loading nodes, now passing again to load the edges" << std::endl;
    if (!load_gfa1_l(gfa_file, g)) {
        std:: cerr << "Error loading gfa1 file's edges " << gfa_file << "\n";
        return 1;
    }

    current_time = time(NULL);
    time_string = ctime(&current_time);
    std::cout << time_string << std::endl;

    // if (!load_gfa1_SL(in, g, &err)) { std::cerr << "error: " << err << "\n"; return 1; }
    std::cerr << "segments: " << g.nodes.size() << ", arcs: " << g.arcs.size() << "\n";
    // Print node0's sequence (if exists)
    if (!g.nodes.empty()) {
        nid_t n_idx;
        auto it = g.id2idx.find(test_node);
        if (it != g.id2idx.end()) {
            n_idx = it->second;
        } else {
            std::cerr << "node0 not found\n";
            return 1;
        }

        std::string seq = node_sequence(&g.nodes[n_idx], false);
        std::cerr << "node " << test_node << " seq (len=" << g.nodes[n_idx].seq_len << "): "
                  << (seq.size() <= 200 ? seq : seq.substr(0,60) + "...") << "\n";

        seq = node_sequence(&g.nodes[n_idx], true);
        std::cerr << "node " << test_node << " reverse seq (len=" << g.nodes[n_idx].seq_len << "): "
                  << (seq.size() <= 200 ? seq : seq.substr(0,60) + "...") << "\n";

        handle_t h = make_handle(n_idx, false);
        std::cerr << "neighbors of node0(+):";
        for_each_neighbor(g, h, [&](const handle_t t){ std::cerr << ' ' << name_of(t, &g) << (is_rev(t)?'-':'+'); });

        h = make_handle(n_idx, true);
        std::cerr << "\nneighbors of node0(+):";
        for_each_neighbor(g, h, [&](const handle_t t){ std::cerr << ' ' << name_of(t, &g) << (is_rev(t)?'-':'+'); });
        std::cerr << "\n";
    }
    return 0;

}
