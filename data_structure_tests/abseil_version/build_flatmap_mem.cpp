#include <iostream>
#include <string>
#include <random>
#include <cstdlib>

#include "absl/container/flat_hash_map.h"

#if defined(__APPLE__)
  #include <mach/mach.h>
#elif defined(__linux__)
  #include <unistd.h>
  #include <fstream>
#endif

// Return current Resident Set Size (RSS) in bytes (0 if unsupported)
static size_t get_rss_bytes() {
#if defined(__APPLE__)
    mach_task_basic_info info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO,
                  reinterpret_cast<task_info_t>(&info), &count) != KERN_SUCCESS) {
        return 0;
    }
    return static_cast<size_t>(info.resident_size);
#elif defined(__linux__)
    long rss_pages = 0;
    std::ifstream f("/proc/self/statm");
    long dummy = 0;
    if (f) { f >> dummy >> rss_pages; }
    long page_size = sysconf(_SC_PAGESIZE);
    return rss_pages > 0 ? static_cast<size_t>(rss_pages) * static_cast<size_t>(page_size) : 0;
#else
    return 0;
#endif
}

static std::string random_string(std::size_t length,
                                 std::mt19937_64 &rng,
                                 std::uniform_int_distribution<std::size_t> &dist) {
    static constexpr char charset[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    static constexpr std::size_t N = sizeof(charset) - 1; // exclude null

    std::string s;
    s.resize(length);
    for (std::size_t i = 0; i < length; ++i) {
        s[i] = charset[dist(rng) % N];
    }
    return s;
}

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);

    if (argc < 2) {
        std::cerr << "Give the number of nodes you want to add to the dict\n";
        return 1;
    }

    const std::size_t n_nodes = static_cast<std::size_t>(std::strtoull(argv[1], nullptr, 10));
    std::size_t key_len = 10; // default like your Python test
    if (argc >= 3) key_len = static_cast<std::size_t>(std::strtoull(argv[2], nullptr, 10));

    // RNG setup
    std::random_device rd;
    std::mt19937_64 rng(rd());
    std::uniform_int_distribution<std::size_t> dist(0, 61);

    // Measure before
    const size_t rss_before = get_rss_bytes();

    // Abseil flat hash map with variable-length string keys
    absl::flat_hash_map<std::string, int> nodes;
    nodes.reserve(n_nodes); // reduce rehashing & peaks

    for (std::size_t i = 0; i < n_nodes; ++i) {
        std::string k = random_string(key_len, rng, dist);

        // Python-like overwrite semantics:
        // try to emplace; if already present, overwrite value
        auto [it, inserted] = nodes.try_emplace(k, static_cast<int>(i));
        if (!inserted) {
            it->second = static_cast<int>(i);
        }
        // (Alternatively: nodes[std::move(k)] = static_cast<int>(i);)
    }

    const size_t rss_after = get_rss_bytes();

    std::cout << nodes.size() << "\n";

    if (rss_before && rss_after && rss_after >= rss_before) {
        const size_t delta = rss_after - rss_before;
        float in_gb = delta/1000000000.0f;
        std::cerr << "Approx RSS increase: " << delta << " bytes\n";
        std::cerr << "Approx RSS increase: " << in_gb << " Gb\n";
        if (!nodes.empty()) {
            std::cerr << "Approx bytes per entry: "
                      << (static_cast<double>(delta) / static_cast<double>(nodes.size()))
                      << "\n";
        }
    } else {
        std::cerr << "(RSS measurement unavailable on this platform or permission denied.)\n";
    }

    return 0;
}

