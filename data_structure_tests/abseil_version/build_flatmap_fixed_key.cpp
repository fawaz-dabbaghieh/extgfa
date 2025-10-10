#include <iostream>
#include <array>
#include <random>
#include <string_view>
#include <cstdlib>

#include "absl/container/flat_hash_map.h"
#include "absl/hash/hash.h"

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

// Fixed-size 10-byte key (exactly your random 10-char ID)
struct Key10 {
    std::array<char, 10> b{};

    // For convenience when hashing, expose as string_view (no allocation)
    std::string_view view() const { return std::string_view(b.data(), b.size()); }

    bool operator==(const Key10& other) const noexcept { return b == other.b; }
};

struct Key20 {
    std::array<char, 20> b{};

    // For convenience when hashing, expose as string_view (no allocation)
    std::string_view view() const { return std::string_view(b.data(), b.size()); }

    bool operator==(const Key20& other) const noexcept { return b == other.b; }
};


// Abseil hasher for Key10 (uses string_view hashing internally)
struct Key10Hash {
    size_t operator()(const Key10& k) const noexcept {
        return absl::Hash<std::string_view>{}(k.view());
    }
};

struct Key20Hash {
    size_t operator()(const Key20& k) const noexcept {
        return absl::Hash<std::string_view>{}(k.view());
    }
};

static Key10 random_key10(std::mt19937_64& rng) {
    static constexpr char charset[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    static constexpr size_t N = sizeof(charset) - 1; // exclude null

    std::uniform_int_distribution<size_t> dist(0, N - 1);
    Key10 k;
    for (size_t i = 0; i < k.b.size(); ++i) {
        k.b[i] = charset[dist(rng)];
    }
    return k;
}


static Key20 random_key20(std::mt19937_64& rng) {
    static constexpr char charset[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    static constexpr size_t N = sizeof(charset) - 1; // exclude null

    std::uniform_int_distribution<size_t> dist(0, N - 1);
    Key20 k;
    for (size_t i = 0; i < k.b.size(); ++i) {
        k.b[i] = charset[dist(rng)];
    }
    return k;
}

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);

    if (argc < 3) {
        std::cerr << "Give the number of nodes you want to add to the dict and 1 for a key length of 10 and 2 for 20\n";
        return 1;
    }
    const std::size_t n_nodes = static_cast<std::size_t>(std::strtoull(argv[1], nullptr, 10));
    const std::size_t key_len = static_cast<std::size_t>(std::strtoull(argv[2], nullptr, 10));

    // RNG
    std::random_device rd;
    std::mt19937_64 rng(rd());

    // Measure before
    const size_t rss_before = get_rss_bytes();

    // Flat, contiguous hash map (no per-element node allocation)
    absl::flat_hash_map<Key10, int, Key10Hash> nodes10;
    absl::flat_hash_map<Key20, int, Key20Hash> nodes20;
    if (key_len == 1) {
        nodes10.reserve(n_nodes);
    } else if (key_len == 2) {
        nodes20.reserve(n_nodes);  // reduces rehashing and peaks
    }


    for (std::size_t i = 0; i < n_nodes; ++i) {
        if (key_len == 1) {
            Key10 k = random_key10(rng);
            nodes10.emplace(k, static_cast<int>(i)); // overwrite behavior isn’t automatic; emulate Python:

        } else if (key_len == 2) {
            Key20 k = random_key20(rng);
            nodes20.emplace(k, static_cast<int>(i)); // overwrite behavior isn’t automatic; emulate Python:

        }

        // If you want overwrite-on-duplicate like Python dict:
        // nodes[k] = static_cast<int>(i);
    }

    const size_t rss_after = get_rss_bytes();

    if (key_len == 1) {
        std::cout << nodes10.size() << "\n";
    } else if (key_len == 2) {
        std::cout << nodes20.size() << "\n";
    }


    if (rss_before && rss_after && rss_after >= rss_before) {
        const size_t delta = rss_after - rss_before;
        float in_gb = delta/1000000000.0f;
        std::cerr << "Approx RSS increase: " << delta << " bytes\n";
        std::cerr << "Approx RSS increase: " << in_gb << " Gb\n";
        // if (!nodes.empty()) {
        //     std::cerr << "Approx bytes per entry: "
        //               << (static_cast<double>(delta) / static_cast<double>(nodes.size()))
        //               << "\n";
        // }
    } else {
        std::cerr << "(RSS measurement unavailable on this platform or permission denied.)\n";
    }

    return 0;
}

