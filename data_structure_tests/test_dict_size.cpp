// build_dict_mem.cpp
#include <iostream>
#include <unordered_map>
#include <string>
#include <random>
#include <vector>
#include <cstdlib>

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
    if (f) {
        f >> dummy >> rss_pages; // total, resident
    }
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
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    static constexpr std::size_t charset_len = sizeof(charset) - 1; // exclude null
    (void)charset_len;

    std::string s;
    s.resize(length);
    for (std::size_t i = 0; i < length; ++i) {
        s[i] = charset[dist(rng)];
    }
    return s;
}

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);

    if (argc < 2) {
        std::cerr << "Give the number of nodes you want to add to the dict\n";
        return 1;
    }

    std::size_t n_nodes = static_cast<std::size_t>(std::strtoull(argv[1], nullptr, 10));
    const std::size_t key_len = 10;

    // Random setup
    std::random_device rd;
    std::mt19937_64 rng(rd());
    // indices 0..61 into charset
    std::uniform_int_distribution<std::size_t> dist(0, 61);

    // Capture RSS before
    size_t rss_before = get_rss_bytes();

    std::unordered_map<std::string, int> nodes;
    // Reserve to reduce rehashing overhead; unordered_map::reserve counts elements.
    nodes.reserve(n_nodes);

    for (std::size_t i = 0; i < n_nodes; ++i) {
        std::string k = random_string(key_len, rng, dist);
        // Emulate Python dict behavior: duplicate keys overwrite (size might be < n_nodes)
        nodes[k] = static_cast<int>(i);
    }

    // Capture RSS after
    size_t rss_after = get_rss_bytes();

    std::cout << nodes.size() << "\n";

    if (rss_before && rss_after && rss_after >= rss_before) {
        size_t delta = rss_after - rss_before;
        std::cerr << "Approx RSS increase: " << delta << " bytes\n";
        if (nodes.size() > 0) {
            double per_entry = static_cast<double>(delta) / static_cast<double>(nodes.size());
            std::cerr << "Approx bytes per entry: " << per_entry << "\n";
        }
    } else {
        std::cerr << "(RSS measurement unavailable on this platform or permission denied.)\n";
    }

    // Keep the map alive until the end so RSS reflects its memory.
    return 0;
}

