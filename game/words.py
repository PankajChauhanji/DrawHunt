"""
Word bank for the drawing game.

`pick_choices` returns a few distinct random words for the drawer to choose
from, avoiding words already used this game where possible.
"""
import random

WORDS = {
    "Indian Vibes": [
        "samosa", "auto rickshaw", "diya", "rangoli", "taj mahal", "kite", 
        "turban", "saree", "bindi", "tabla", "sitar", "cricket bat", 
        "chai", "jalebi", "dosa", "idli", "mango", "banyan tree", "lotus", 
        "peacock", "thali", "chapati", "pani puri", "ganesha", "kulfi", 
        "bangles", "mehndi", "coconut", "sugarcane", "marigold", "tandoor", 
        "jhula", "charpai", "ludo", "carrom board", "dhoti", "flute", 
        "matka", "gulab jamun", "vada pav", "charkha", "india gate", 
        "stumps", "rickshaw", "pagdi", "kalash", "ghunghroo", "agarbatti"
    ],
    
    "Everyday Objects": [
        "guitar", "umbrella", "ladder", "candle", "bicycle", "anchor",
        "balloon", "camera", "clock", "envelope", "glasses", "hammer", 
        "lamp", "mirror", "pencil", "scissors", "spoon", "telephone", 
        "toothbrush", "wallet", "basket", "bucket", "button", "compass", 
        "drum", "feather", "spectacles", "key", "lock", "backpack", 
        "teapot", "frying pan", "iron", "comb", "towel", "soap", "needle", 
        "matchbox", "knife", "fork", "plate", "bowl", "cup", "bottle", 
        "vase", "watch", "ring", "necklace", "earring", "hat", "cap", 
        "scarf", "gloves", "socks", "shoes", "boots", "slippers", "belt", 
        "tie", "book", "notebook", "newspaper", "painting", "calendar", 
        "map", "globe", "pillow", "blanket", "chair", "table", "sofa"
    ],

    "Animals & Birds": [
        "elephant", "penguin", "octopus", "giraffe", "kangaroo", "butterfly",
        "dolphin", "hedgehog", "ostrich", "squirrel", "tiger", "turtle", 
        "whale", "snail", "spider", "rabbit", "rooster", "frog", "shark", 
        "owl", "lion", "bear", "monkey", "zebra", "panda", "rhino", "hippo", 
        "crocodile", "snake", "lizard", "chameleon", "bat", "mouse", "dog", 
        "cat", "cow", "horse", "pig", "sheep", "goat", "chicken", "duck", 
        "swan", "pigeon", "crow", "parrot", "woodpecker", "eagle", "flamingo", 
        "pelican", "crab", "lobster", "starfish", "seahorse", "jellyfish"
    ],

    "Food & Drinks": [
        "pizza", "hamburger", "ice cream", "pancake", "popcorn", "watermelon",
        "cupcake", "donut", "pineapple", "sandwich", "cheese", "carrot", 
        "banana", "apple", "orange", "grape", "strawberry", "lemon", "cherry", 
        "peach", "pear", "kiwi", "papaya", "tomato", "potato", "onion", 
        "garlic", "mushroom", "broccoli", "corn", "peanut", "bread", "cake", 
        "pie", "cookie", "muffin", "croissant", "pretzel", "pasta", "noodle", 
        "rice", "soup", "salad", "steak", "fish", "egg", "bacon", "sausage", 
        "milk", "juice", "coffee", "tea", "soda", "wine", "boba tea", "honey"
    ],

    "Nature & Places": [
        "mountain", "rainbow", "volcano", "island", "waterfall", "lighthouse",
        "cactus", "snowman", "campfire", "tornado", "bridge", "castle", 
        "windmill", "tree", "flower", "grass", "leaf", "rock", "sand", 
        "puddle", "river", "lake", "ocean", "wave", "beach", "desert", 
        "forest", "jungle", "cave", "cliff", "valley", "sun", "moon", "star", 
        "cloud", "rain", "snow", "lightning", "storm", "earthquake", "city", 
        "village", "street", "road", "highway", "park", "garden", "farm", 
        "barn", "house", "apartment", "skyscraper", "school", "hospital", 
        "library", "museum", "church", "temple", "mosque", "tent"
    ],

    "Vehicles & Transport": [
        "airplane", "rocket", "submarine", "helicopter", "tractor", "sailboat",
        "train", "scooter", "ambulance", "skateboard", "car", "truck", "bus", 
        "van", "motorcycle", "tricycle", "unicycle", "roller skates", 
        "snowboard", "surfboard", "boat", "ship", "ferry", "yacht", "canoe", 
        "kayak", "raft", "hot air balloon", "ufo", "carriage", "wagon", 
        "cart", "sled", "bulldozer", "crane", "fire engine", "police car", 
        "taxi", "tow truck", "garbage truck", "parachute"
    ],

    "Sports & Games": [
        "football", "basketball", "baseball", "tennis", "volleyball", 
        "golf", "hockey", "cricket", "badminton", "table tennis", "boxing", 
        "wrestling", "fencing", "archery", "weightlifting", "gymnastics", 
        "swimming", "diving", "surfing", "sailing", "cycling", "running", 
        "skiing", "ice skating", "bowling", "billiards", "darts", "chess", 
        "dice", "puzzle", "rubik's cube", "video game", "joystick", "trophy", 
        "medal", "whistle", "boxing gloves", "tennis racket", "golf club"
    ],

    "Technology & Science": [
        "computer", "laptop", "tablet", "smartphone", "smartwatch", 
        "television", "radio", "speaker", "headphones", "microphone", 
        "printer", "keyboard", "mouse", "monitor", "battery", "charger", 
        "plug", "lightbulb", "laser", "robot", "drone", "satellite", 
        "telescope", "microscope", "atom", "dna", "virus", "brain", "heart", 
        "lung", "stomach", "bone", "skull", "skeleton", "muscle", "eye", 
        "ear", "nose", "mouth", "tooth", "tongue", "magnet", "thermometer", 
        "syringe", "flask", "beaker"
    ],

    "History & Fantasy": [
        "dinosaur", "fossil", "pyramid", "mummy", "sphinx", "chariot", 
        "knight", "armor", "sword", "shield", "bow", "arrow", "spear", 
        "axe", "catapult", "king", "queen", "crown", "throne", "dragon", 
        "unicorn", "pegasus", "mermaid", "centaur", "cyclops", "troll", 
        "goblin", "fairy", "ghost", "vampire", "werewolf", "zombie", 
        "witch", "wizard", "magic wand", "potion", "broomstick", 
        "cauldron", "crystal ball", "treasure chest", "pirate"
    ],

    "Actions & Concepts": [
        "dancing", "sleeping", "swimming", "singing", "fishing", "juggling",
        "painting", "running", "cooking", "reading", "crying", "laughing", 
        "jumping", "climbing", "shouting", "kicking", "punching", "sneezing", 
        "yawning", "typing", "sweeping", "digging", "flying", "falling", 
        "pushing", "pulling", "hugging", "kissing", "praying", "bathing"
    ],
    
    "Professions & Roles": [
        "doctor", "chef", "police", "teacher", "farmer", "astronaut", 
        "pilot", "painter", "singer", "magician", "clown", "judge", 
        "thief", "ninja", "diver", "barber", "tailor", "photographer", 
        "mechanic", "firefighter", "plumber", "scientist", "baker", 
        "soldier", "detective", "waiter", "dentist", "postman", "butcher"
    ],

    "Monuments & Landmarks": [
        "eiffel tower", "statue of liberty", "taj mahal", "qutub minar", 
        "pyramid", "great wall of china", "gateway of india", "igloo", 
        "leaning tower", "sydney opera house", "lighthouse", "windmill", 
        "red fort", "charminar", "golden temple", "big ben", "colosseum", 
        "stonehenge", "mount rushmore", "hawa mahal", "india gate"
    ],

    "School & Office Days": [
        "blackboard", "chalk", "school bus", "backpack", "calculator", 
        "briefcase", "desk", "whiteboard", "globe", "microscope", "bell", 
        "diploma", "eraser", "ruler", "compass", "lunchbox", "water bottle", 
        "stapler", "paperclip", "pushpin", "clipboard", "highlighter", 
        "file cabinet", "swivel chair", "water cooler", "projector"
    ],

    "Emotions & Expressions": [
        "happy", "sad", "angry", "crying", "laughing", "shocked", 
        "sleeping", "thinking", "tired", "scared", "confused", "dizzy", 
        "sweating", "freezing", "in love", "sick", "yawning", "winking", 
        "blushing", "bored", "nervous", "screaming", "smiling", "frowning"
    ],

    "Space & Universe": [
        "sun", "moon", "star", "earth", "saturn", "alien", "ufo", 
        "rocket", "satellite", "telescope", "comet", "asteroid", "galaxy", 
        "black hole", "rover", "space station", "meteor", "milky way", 
        "orbit", "solar system", "constellation", "eclipse", "astronaut"
    ],

    "Movies & Entertainment": [
        "film reel", "popcorn", "3d glasses", "director chair", 
        "clapperboard", "megaphone", "trophy", "red carpet", "theater", 
        "ticket", "microphone", "magic trick", "mask", "stage", "curtain", 
        "spotlight", "camera", "script", "cinema", "stunt", "puppet"
    ],
    
    "Festivals & Celebrations": [
        "firework", "gift", "balloon", "cake", "party hat", "confetti", 
        "diya", "rangoli", "pichkari", "water gun", "rakhi", "christmas tree", 
        "santa claus", "snowman", "pumpkin", "jack-o-lantern", "wedding", 
        "ring", "groom", "bride", "garland", "ribbon", "sparkler", "bonfire",
        "mehendi", "dandiya", "kalash", "modak"
    ],

    "Music & Instruments": [
        "guitar", "piano", "drum", "flute", "violin", "trumpet", "saxophone", 
        "harp", "tabla", "sitar", "harmonium", "dholak", "microphone", 
        "headphones", "speaker", "musical note", "cassette", "cd", "radio", 
        "gramophone", "conductor", "singer", "whistle", "boombox", "mp3 player"
    ],

    "Clothing & Fashion": [
        "t-shirt", "jeans", "shorts", "dress", "skirt", "sweater", "jacket", 
        "coat", "socks", "shoes", "boots", "sandals", "heels", "hat", "cap", 
        "scarf", "gloves", "tie", "belt", "glasses", "sunglasses", "watch", 
        "necklace", "ring", "earring", "bracelet", "purse", "wallet", 
        "saree", "kurta", "dhoti", "turban", "bindi", "lehenga", "dupatta"
    ],

    "Toys & Hobbies": [
        "teddy bear", "doll", "action figure", "lego", "puzzle", 
        "rubik's cube", "yo-yo", "spinning top", "lattu", "kite", "marble", 
        "slingshot", "toy car", "train set", "rocking horse", "jump rope", 
        "swing", "slide", "seesaw", "paintbrush", "palette", "clay", 
        "origami", "knitting", "stamp", "telescope"
    ],

    "Body Parts & Anatomy": [
        "eye", "nose", "mouth", "ear", "hair", "hand", "foot", "arm", 
        "leg", "finger", "toe", "thumb", "nail", "tooth", "tongue", 
        "brain", "heart", "bone", "skeleton", "skull", "muscle", 
        "footprint", "handprint", "mustache", "beard", "lips"
    ]
}

# Pre-flatten the list and remove duplicates. 
# Using set() ensures words that appear in multiple categories are only loaded once.
FLAT_WORDS_POOL = list(set(word for theme_list in WORDS.values() for word in theme_list))
print(len(FLAT_WORDS_POOL), "unique words loaded into the pool.")

def pick_choices(n: int, exclude: set[str] | None = None) -> list[str]:
    """
    Selects `n` random words from the global pool, ignoring those in `exclude`.
    """
    exclude = exclude or set()
    
    # Filter out words that have already been played this game
    pool = [w for w in FLAT_WORDS_POOL if w not in exclude]
    
    # If we somehow run out of fresh words, reset the pool to all words
    if len(pool) < n:               
        pool = FLAT_WORDS_POOL
        
    return random.sample(pool, min(n, len(pool)))