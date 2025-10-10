import random
import string
import sys


nodes = dict()

if len(sys.argv) < 2:
    print("Give the number of nodes you want to add to the dict")
    sys.exit()

n_nodes = int(sys.argv[1])

def generate_random_string(length):
    """
    Generates a random string of a specified length using alphanumeric characters.
    """
    # Define the set of characters to choose from (letters and digits)
    characters = string.ascii_letters + string.digits
    # Use random.choice to pick characters and join them to form the string
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

length = 10
for i in range(n_nodes):
    n_id = generate_random_string(length)
    nodes[n_id] = i

print(len(nodes))
