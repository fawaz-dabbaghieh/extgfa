//
// Created by Fawaz Dabbaghie on 10/09/2025.
//

#ifndef CHUNKEDGFA_DIS_GFA_PARSER_H
#define CHUNKEDGFA_DIS_GFA_PARSER_H
#include <string>


struct Tag {
    std::string id;
    std::string type;
    std::string value;
};

struct Edge {
    std::string to_name;
    std::string overlap;
    bool rev;
    std::vector<Tag> tags;
};

struct Node {
    // std::vector<uint64_t> seq_words; // packed 2-bit bases, little-endian per word
    std::string seq;
    std::string name;
    size_t seq_len = 0;              // length in bases
    // so if the edge in out_handle has the lowest bit as 0
    // then this edge's is the current node name + out_handle name + overlap and other tags
    std::vector<Edge> out_edges;
    std::vector<Edge> in_edges;
    std::vector<Tag> tags;
};


struct Graph {
    std::unordered_map<std::string, Node> Nodes;
};


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

// Parse an S-line in-place: get <name> and sequence length only.
// line is like: "S\t<name>\t<seq>\t<tag1>\t..."
inline bool parse_s_line(const std::string& line,
    Node* n,
    const bool low_mem) {

    const size_t i = 2; // after "S\t"
    const size_t t1 = line.find('\t', i);

    if (t1 == std::string::npos) {
        return false;
    }

    n->name = std::string_view(line.data() + i, t1 - i);

    const size_t t2 = t1 + 1;                   // start of <seq>
    const size_t t3 = line.find('\t', t2);    // end of <seq> or npos
    if (!low_mem) {
        n->seq = std::string_view(line.data() + t2, t3 - t2);
        n->seq_len = n->seq.size();
    } else {
        size_t end = (t3 == std::string::npos ? line.size() : t3);
        // strip trailing CR if present on the line
        if (end && line[end-1] == '\r') --end;

        if (t2 < end) n->seq_len = static_cast<uint32_t>(end - t2);
        else n->seq_len = 0; // '*' case or empty
    }
    return true;
}


inline bool parse_l_line(Graph* in_graph, const std::string& line) {
    // this function needs to read the L line of a GFA file and create an edge that is added to both nodes
    const size_t i = 2; // after "L\t"

    return true;
}

#endif //CHUNKEDGFA_DIS_GFA_PARSER_H