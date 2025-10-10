//
// Created by Fawaz Dabbaghie on 10/09/2025.
//

#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <sstream>
#include "dis_gfa_parser.h"



using namespace std;


int main(int argc, char** argv) {
    if (argc < 3) { std::cerr << "usage: " << argv[0] << " file.gfa test_node_id\n"; return 1; }
    std::string gfa_file = argv[1];
    std::string test_node = argv[2];
    std::cerr << "Input GFA file: " << gfa_file << std::endl;
    std::cerr << "test_node: " << test_node << std::endl;
    std::string line;
    int lineno = 0;
    std::ifstream in(gfa_file);
    while (std::getline(in, line)) {
        ++lineno;
        if (line.empty() || line[0] == '#') continue;
        if (line[0] == 'S') {
            Node n;
            if (!parse_s_line(line, &n, false)) {
                std::cerr << "malformed S record at line " << lineno << ": " << line << "\n";
            } else {
                std::cerr << "name: " << n.name << "\n";
                std::cerr << "seq: " << n.seq << "\n";
                std::cerr << "seq_len: " << n.seq_len << "\n";
            }
            // no copies: use name/seq directly
            // e.g. only length: uint32_t len = static_cast<uint32_t>(seq.size());
        }
    }

    in.close();

    // string filename = "/Users/fawaz/projects/gfa_parser/example_files/component10_gxx.txt";
    // ifstream in2(filename);
    // if (!in2) {
    //     cerr << "Error: Unable to open file " << filename << "\n";
    //     return 1;
    // }

    return 0;
}
