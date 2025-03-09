## https://adventofcode.com/2017/day/3

# You come across an experimental new kind of memory stored on an infinite two-dimensional grid.

# Each square on the grid is allocated in a spiral pattern starting at a location marked 1 and then counting up while spiraling outward. For example, the first few squares are allocated like this:

# 17  16  15  14  13
# 18   5   4   3  12
# 19   6   1   2  11
# 20   7   8   9  10
# 21  22  23---> ...
# While this is very space-efficient (no squares are skipped), requested data must be carried back to square 1 (the location of the only access port for this memory system) by programs that can only move up, down, left, or right. They always take the shortest path: the Manhattan Distance between the location of the data and square 1.

# For example:

# Data from square 1 is carried 0 steps, since it's at the access port.
# Data from square 12 is carried 3 steps, such as: down, left, left.
# Data from square 23 is carried only 2 steps: up twice.
# Data from square 1024 must be carried 31 steps.
# How many steps are required to carry the data from the square identified in your puzzle input all the way to the access port?

# Your puzzle input is 325489.

## Part 1
import math

def steps_to_port(num):
  if num == 1: 
    return 0

  max_side_length = math.ceil(num ** 0.5)
  if max_side_length % 2 == 0:
    max_side_length += 1

  ring_num = (max_side_length-1) // 2 # Distance from center at the outermost ring
  ## Note: ring_num is the minimum possible distance to the center (straight line)
  ## The max possible distance is ring_num*2 (ie from the corner)
  steps_back = max_side_length**2 - num ## diff from number/steps back needed (around the ring)
  side_steps = max_side_length-1 # length of one side excluding corners

  offset = steps_back % side_steps ## distince from nearest corner

  # if offset == 0 : # covers all corner points
  #   steps_from_center = ring_num
  # elif offset == ring_num: ## covers all center points of each side of the Square
  #   steps_from_center = 0
  # elif offset < ring_num: ## if steps are less than half, take steps to get to center of side
  #   steps_from_center = ring_num - offset
  # elif offset > ring_num: ## if steps are great than half ,take steps to closest center of side
  #   steps_from_center = offset - ring_num
  steps_from_center = abs(offset - ring_num)

  steps = ring_num + steps_from_center
  return steps

#steps_to_port(325489)
# 552

# --- Part Two ---
# As a stress test on the system, the programs here clear the grid and then store the value 1 in square 1. Then, in the same allocation order as shown above, they store the sum of the values in all adjacent squares, including diagonals.

# So, the first few squares' values are chosen as follows:

# Square 1 starts with the value 1.
# Square 2 has only one adjacent filled square (with value 1), so it also stores 1.
# Square 3 has both of the above squares as neighbors and stores the sum of their values, 2.
# Square 4 has all three of the aforementioned squares as neighbors and stores the sum of their values, 4.
# Square 5 only has the first and fourth squares as neighbors, so it gets the value 5.
# Once a square is written, its value does not change. Therefore, the first few squares would receive the following values:

# 147  142  133  122   59
# 304    5    4    2   57
# 330   10    1    1   54
# 351   11   23   25   26
# 362  747  806--->   ...
# What is the first value written that is larger than your puzzle input?

## Part 2

## Gave up on this, I think the easiest coding/computational way is to make the matrix and sum
## but I wanted to find a direct solution/got stuck on the math/logic of it.


## ChatGPT + explanations (avoiding creating the full matrix)
from itertools import count
from collections import defaultdict
# defaultdict(int): Automatically initializes missing values as 0 (avoiding key errors).
# count(1, 2): Generates an increasing sequence (1, 3, 5, 7, ...) to control how far we move in each step.

def sum_spiral():
    a, x, y = defaultdict(int), 0, 0
    a[(0, 0)] = 1  # Starting value

    ## This function returns the sum of all values in the 8 adjacent squares (ie incomplete are just empty)
    def get_adjacent_sum(x, y):
        return sum(a[(dx, dy)] for dx in range(x - 1, x + 2)
                                  for dy in range(y - 1, y + 2))

    for step in count(1, 2):  # Expands outward in spiral
        for _ in range(step):    # Move right
            x += 1
            a[(x, y)] = get_adjacent_sum(x, y)
            yield a[(x, y)]
        for _ in range(step):    # Move up
            y -= 1
            a[(x, y)] = get_adjacent_sum(x, y)
            yield a[(x, y)]
        for _ in range(step + 1):  # Move left
            x -= 1
            a[(x, y)] = get_adjacent_sum(x, y)
            yield a[(x, y)]
        for _ in range(step + 1):  # Move down
            y += 1
            a[(x, y)] = get_adjacent_sum(x, y)
            yield a[(x, y)]

def part2(n):
    for value in sum_spiral():
        if value > n:
            return value

part2(325489)
## 330785
