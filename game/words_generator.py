import json

# ==========================================
# 1. ENGLISH WORD BANK
# ==========================================
ENGLISH_WORDS = {
    "Animals": "elephant, giraffe, kangaroo, hedgehog, squirrel, tiger, bear, monkey, zebra, panda, rhino, hippo, snake, lizard, chameleon, bat, mouse, dog, cat, cow, horse, pig, sheep, goat, badger, chipmunk, ferret, gerbil, hamster, lemur, meerkat, mongoose, opossum, tapir, weasel, yak, alpaca, llama, camel, gazelle, antelope, bison, reindeer, elk, baboon, orangutan, cheetah, panther, hyena, wolf, fox, otter, gorilla, chimpanzee, koala, wombat, platypus, armadillo, porcupine, beaver, moose, raccoon, skunk, sloth",
    "Birds": "ostrich, penguin, rooster, owl, chicken, duck, swan, pigeon, crow, parrot, woodpecker, eagle, flamingo, pelican, albatross, canary, cockatoo, crane, dove, finch, heron, hummingbird, ibis, kingfisher, macaw, oriole, parakeet, peafowl, puffin, raven, robin, seagull, sparrow, stork, swallow, toucan, turkey, vulture",
    "Sea Life": "octopus, dolphin, turtle, whale, frog, shark, crocodile, crab, lobster, starfish, seahorse, jellyfish, walrus, seal, anemone, barnacle, clam, conch, eel, flounder, koi, manatee, manta ray, marlin, narwhal, oyster, piranha, pufferfish, salmon, scallop, squid, stingray, swordfish, tadpole",
    "Insects": "butterfly, snail, spider, ladybug, bee, ant, beetle, caterpillar, moth, worm, grasshopper, scorpion",
    "Food": "pizza, hamburger, pancake, sandwich, cheese, carrot, tomato, potato, onion, garlic, mushroom, broccoli, corn, peanut, bread, pasta, noodle, rice, soup, salad, steak, fish, egg, bacon, sausage, sushi, taco, burrito, hotdog, waffle, pickle, olive, dumpling, celery, cucumber, eggplant, lettuce, pumpkin, radish, spinach, zucchini, nachos, chips, cracker",
    "Fruits": "watermelon, pineapple, banana, apple, orange, grape, strawberry, lemon, cherry, peach, pear, kiwi, papaya, avocado, mango, coconut",
    "Desserts": "ice cream, cupcake, donut, cake, pie, cookie, muffin, croissant, pretzel, lollipop, chocolate, marshmallow, pudding, brownie, jelly, popsicle, caramel, crepe, churro, chewing gum, cotton candy, macaron, tart, cheesecake",
    "Drinks": "milk, juice, coffee, tea, soda, wine, honey",
    "Nature": "mountain, rainbow, volcano, island, waterfall, cactus, snowman, campfire, tornado, tree, flower, grass, leaf, rock, sand, puddle, river, lake, ocean, wave, beach, desert, forest, jungle, cave, cliff, valley, sun, moon, star, cloud, rain, snow, lightning, storm, earthquake, acorn, pinecone, log, twig, pebble, swamp, canyon, iceberg",
    "Places": "bridge, castle, windmill, lighthouse, city, village, street, road, highway, park, garden, farm, barn, house, apartment, skyscraper, tent, garage, driveway, attic, basement, porch, balcony",
    "Vehicles": "airplane, rocket, submarine, helicopter, tractor, sailboat, train, scooter, ambulance, skateboard, car, truck, bus, van, motorcycle, tricycle, unicycle, snowboard, surfboard, boat, ship, ferry, yacht, canoe, kayak, raft, carriage, wagon, cart, sled, bulldozer, crane, taxi, parachute, blimp, hovercraft, jetski, gondola, forklift",
    "Sports": "football, basketball, baseball, tennis, volleyball, golf, hockey, cricket, badminton, boxing, wrestling, fencing, archery, weightlifting, gymnastics, swimming, diving, surfing, sailing, cycling, running, skiing, bowling, billiards, darts, trophy, medal, whistle",
    "Games": "chess, dice, puzzle, joystick, dartboard, domino, marble, rubiks cube, jigsaw puzzle, video game",
    "Technology": "computer, laptop, tablet, smartphone, smartwatch, television, radio, speaker, headphones, microphone, printer, keyboard, mouse, monitor, battery, charger, plug, lightbulb, laser, robot, drone, satellite, telescope, microscope, magnet, thermometer, syringe, flask, beaker, tripod, webcam",
    "History": "dinosaur, fossil, pyramid, mummy, sphinx, chariot, knight, armor, sword, shield, bow, arrow, spear, axe, catapult, king, queen, crown, throne, pirate",
    "Fantasy": "dragon, unicorn, pegasus, mermaid, centaur, cyclops, troll, goblin, fairy, ghost, vampire, werewolf, zombie, witch, wizard, potion, broomstick, cauldron, griffin, phoenix, kraken, medusa, minotaur, genie, yeti, sasquatch, leprechaun, wand",
    "Professions": "doctor, chef, police, teacher, farmer, astronaut, pilot, painter, singer, magician, clown, judge, thief, ninja, diver, barber, tailor, photographer, mechanic, firefighter, plumber, scientist, baker, soldier, detective, waiter, dentist, postman, butcher",
    "Body Parts": "eye, nose, mouth, ear, hair, hand, foot, arm, leg, finger, toe, thumb, nail, tooth, tongue, brain, heart, bone, skull, footprint, handprint, mustache, beard, lips",
    "Music": "guitar, piano, drum, flute, violin, trumpet, saxophone, harp, microphone, headphones, speaker, cassette, radio, gramophone, conductor, singer, whistle, boombox, banjo, cello, tuba, trombone, xylophone, accordion, ukulele, maracas, tambourine, gong, bagpipes, didgeridoo, kazoo",
    "Art": "palette, paintbrush, clay, origami, easel, canvas, sketchbook, painting",
    "House": "bed, bathtub, toilet, sink, oven, dishwasher, fireplace, chimney, window, door, stairs, roof, fence, mailbox, doorknob, hanger, plunger, toothpaste, bookshelf, carpet, curtain, radiator, thermostat, doorbell, doormat, lampshade, mattress, nightstand, chandelier, birdhouse, hammock, toaster, blender, microwave, fridge, couch, rug, sponge, broom, mop, trashcan",
    "Objects": "umbrella, ladder, candle, bicycle, anchor, balloon, camera, clock, envelope, glasses, hammer, lamp, mirror, pencil, scissors, spoon, telephone, toothbrush, wallet, basket, bucket, button, compass, drum, feather, spectacles, key, lock, backpack, teapot, iron, comb, towel, soap, needle, matchbox, knife, fork, plate, bowl, cup, bottle, vase, watch, ring, necklace, earring, hat, cap, scarf, gloves, socks, shoes, boots, slippers, belt, tie, book, notebook, newspaper, calendar, map, globe, pillow, blanket, chair, table, sofa, tape, stapler, paperclip, clipboard, highlighter, purse, coin",
    "Tools": "wrench, screwdriver, pliers, saw, drill, hardhat, brick, cement, wheelbarrow, chainsaw, anvil, bolt, screw, clamp, crowbar, mallet, pickaxe, pitchfork, rake, shovel, trowel, scaffolding, jackhammer, toolbox, sandpaper",
    "Clothing": "sweater, jacket, sandals, heels, sunglasses, bracelet, tiara, bowtie, overalls, tuxedo, pajamas, raincoat, apron, helmet, zipper, pocket, shoelace, vest, badge, underwear, swimsuit, bikini, earmuffs, mittens, suspenders, bathrobe, hoodie, poncho",
    "Toys": "teddy bear, doll, lego, yoyo, kite, slingshot, swing, slide, seesaw, trampoline, binoculars, boomerang, frisbee, pogo stick, hula hoop, unicycle",
    "Space": "astronaut, alien, ufo, rocket, satellite, rover, observatory, telescope, galaxy, black hole, meteor, spacesuit",
    "Science": "dna, test tube, beaker, bunsen burner, goggles, petri dish, syringe, thermometer, atom",
    "Shapes": "circle, square, triangle, heart, diamond, cross, arrow, spiral, zigzag, infinity, checkmark, star, crescent, hexagon, octagon, pentagon, oval, cylinder, cube, pyramid",
    "Actions": "running, jumping, swimming, sleeping, crying, laughing, singing, dancing, fishing, cooking, reading, painting, climbing, digging, flying, falling, hugging, kissing, kicking, punching, sneezing, yawning, pointing, waving, clapping, juggling, crawling"
}

# ==========================================
# 2. HINDI / INDIAN CONTEXT WORD BANK
# ==========================================
HINDI_WORDS = {
    "Food": "samosa, chai, jalebi, dosa, idli, thali, chapati, pani puri, bhel puri, pav bhaji, chole bhature, paratha, thepla, dhokla, momos, kachori, pakora, biryani, khichdi, papad, achar, chutney, ghee, besan, kathi roll, kulcha, mathri, fafda, khandvi, appam, puttu, upma, poha, sabudana, makhana, paan, supari, lassi, paneer, naan, bhatura, roti",
    "Desserts": "kulfi, gulab jamun, vada pav, rasgulla, rasmalai, peda, soan papdi, ghevar, chamcham, boondi, petha, gujiya, falooda, gajak, chikki, malpua, shrikhand, halwa, laddu, barfi, modak",
    "House": "jhula, charpai, matka, belan, chakla, tawa, kadhai, balti, lota, channi, silbatta, okhli, katori, chamcha, jhadu, pocha, tokri, machhardani, chatai, palang, takiya, rajai, kambal, mudda, bartan, dabba, sandasi, karchhi, patila, bhagona, kalsa",
    "Objects": "diya, rangoli, kite, bindi, bangles, mehndi, tandoor, charkha, kalash, agarbatti, lifafa, tijori, chata, aaina, kanghi, sindoor, kajal, alta, mela, phataka, anaar, chakri, phuljhadi, dhoop, kapoor, hookah, rumal, potli, batwa, pichkari, rakhi, dandiya, lattu, chimta",
    "Clothing": "turban, saree, dhoti, pagdi, sherwani, kurti, dupatta, petticoat, salwar, kameez, lungi, gamcha, safa, jutti, ghagra, choli, mangalsutra, nath, jhumka, choodi, bajuband, kamarband, gajra, mojari, bichhiya, maang tikka, burqa, kurta, lehenga, ghoonghat",
    "Culture & Religion": "ganesha, puja, aarti, prasad, havan, kund, chandan, haldi, kumkum, moli, rudraksh, mala, shankh, ghanti, trishul, damaru, pandal, murti, holika, gulal, dahi handi, garba, bhangra, kathputli, namaste",
    "Vehicles": "auto rickshaw, rickshaw, auto, thela, tonga, bailgadi, hathgadi, doli, palki, rath, naav",
    "Music": "tabla, sitar, ghunghroo, harmonium, dholak, bansuri, ektara, sarangi, dhol, nagada, shehnai, pungi, been, payal",
    "Places": "taj mahal, india gate, khet, bagicha, maidan, nukkad, chauraha, gali, haweli, kuan, nahar, aangan, chhat",
    "Tools": "kulhadi, phawda, kudal, khurpi, darati, hathodi",
    "Nature": "banyan tree, lotus, marigold, tulsi, neem, peepal, pudina, dhania, nimbu, pyaj, lahsun, adrak, mirchi, tamatar, aaloo, baingan, karela, bhindi, lauki, kaddu, mooli, gajar, matar",
    "Animals": "peacock, kauwa, kabootar, tota, mor, macchar, makkhi, chhipkali, chuha, bandar, bhalu, hathi, sher, lomdi, hiran, gai, bhains, bakri, bhed, gadha, ghoda, unt, kutta, billi"
}

# ==========================================
# 3. JSON GENERATOR LOGIC
# ==========================================
word_tracker = {}

def process_word_dict(word_dictionary: dict, lang_code: str):
    """Parses a dictionary and adds words to the global tracking map."""
    for theme, word_string in word_dictionary.items():
        # Split by comma and clean up spaces
        words = [w.strip() for w in word_string.split(",")]
        
        for word in words:
            if not word: 
                continue 
            
            # If the word is new, initialize it
            if word not in word_tracker:
                word_tracker[word] = {
                    "word": word,
                    "lang": lang_code,
                    "themes": [theme]
                }
            else:
                # If word already exists, append the new theme
                if theme not in word_tracker[word]["themes"]:
                    word_tracker[word]["themes"].append(theme)

# Run both dictionaries through the processor
process_word_dict(ENGLISH_WORDS, "eng")
process_word_dict(HINDI_WORDS, "hin")

# Convert tracking dictionary to a flat list
final_word_bank = list(word_tracker.values())

# Export to words.json
with open('words.json', 'w', encoding='utf-8') as f:
    json.dump(final_word_bank, f, indent=2)

print(f"Success! Processed {len(final_word_bank)} distinct words into 'words.json'.")