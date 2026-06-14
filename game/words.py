"""
Word bank for the drawing game.

`pick_choices` returns a few distinct random words for the drawer to choose
from, avoiding words already used this game where possible.
"""
import random

WORDS = [
    # everyday objects
    "apple", "guitar", "umbrella", "ladder", "candle", "bicycle", "anchor",
    "balloon", "camera", "clock", "envelope", "glasses", "hammer", "kite",
    "lamp", "mirror", "pencil", "scissors", "spoon", "telephone", "toothbrush",
    "wallet", "basket", "bucket", "button", "compass", "drum", "feather",
    # animals
    "elephant", "penguin", "octopus", "giraffe", "kangaroo", "butterfly",
    "dolphin", "hedgehog", "ostrich", "squirrel", "tiger", "turtle", "whale",
    "snail", "spider", "rabbit", "rooster", "frog", "shark", "owl",
    # food
    "pizza", "hamburger", "ice cream", "pancake", "popcorn", "watermelon",
    "cupcake", "donut", "pineapple", "sandwich", "cheese", "carrot", "banana",
    # nature & places
    "mountain", "rainbow", "volcano", "island", "waterfall", "lighthouse",
    "cactus", "snowman", "campfire", "tornado", "bridge", "castle", "windmill",
    # vehicles
    "airplane", "rocket", "submarine", "helicopter", "tractor", "sailboat",
    "train", "scooter", "ambulance", "skateboard",
    # actions / concepts
    "dancing", "sleeping", "swimming", "singing", "fishing", "juggling",
    "painting", "running", "cooking", "reading",
    # misc fun
    "robot", "dragon", "ghost", "pirate", "wizard", "mermaid", "dinosaur",
    "astronaut", "vampire", "superhero", "treasure", "crown", "guitar",
]


def pick_choices(n: int, exclude: set[str] | None = None) -> list[str]:
    exclude = exclude or set()
    pool = [w for w in set(WORDS) if w not in exclude]
    if len(pool) < n:               # ran out of fresh words; reuse the full set
        pool = list(set(WORDS))
    return random.sample(pool, min(n, len(pool)))