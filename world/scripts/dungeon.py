from evennia import DefaultScript, create_object, search_object
import time
from evennia.objects.models import ObjectDB 

class DungeonManager(DefaultScript):

    def at_script_creation(self):
        self.key = "dungeon_manager"
        self.desc = "Manages all active dungeons."
        self.persistent = True
        self.interval = 31  # Check all dungeons every 120 seconds (at_repeat)
        self.db.expire_time = 60 # Expiry time in seconds (default: 20 mins)
        self.db.active_dungeons = {}  # Dictionary to store dungeons by name or ID
    
    def at_repeat(self):
        """
        Called at every repeat interval.
        """
        # Used to check if the dungeon should be deleted
        current_time = time.time()
        active_dungeons = self.db.active_dungeons

        if not active_dungeons:
            return

        for dungeon in active_dungeons:
            dungeon_creator = active_dungeons[dungeon].db.dungeon_attributes["creator"]
            creator = ObjectDB.objects.get(db_key=dungeon_creator)
            name = active_dungeons[dungeon].db.dungeon_attributes["template_name"]
            dungeon_start_time = active_dungeons[dungeon].db.dungeon_attributes["start_time"]
            elapsed_time = current_time - dungeon_start_time

            if elapsed_time >= self.db.expire_time:
                print(f"Time has expired.")
                # Check if the creator is still in the dungeon
                if not self.creator_in_dungeon(creator, dungeon):
                    print(f"Deleting the dungeon named: {name}")
                    self.delete_dungeon(active_dungeons[dungeon].dbref)

    def creator_in_dungeon(self, creator, dungeon):
        """
        Check if the creator is in any of the rooms of the dungeon.

        Args:
            creator (Object): The character who created the dungeon.
            dungeon (Object): The dungeon object storing the room data.

        Returns:
            bool: True if the creator is in any of the dungeon rooms, False otherwise.
        """
        found = False
        active_dungeons = self.db.active_dungeons
        name = active_dungeons[dungeon].db.dungeon_attributes["template_name"]
        id = active_dungeons[dungeon].dbref
        result = search_object(id)
        obj = result[0]
        # Get the list of rooms from the dungeon's attributes
        dungeon_rooms = obj.attributes.get("dungeon_attributes", {}).get("rooms", [])
        # Check if the creator's location matches any of the dungeon rooms
        for room in dungeon_rooms.values():
            if creator.location == room:
                print(f"{creator} is in {name}")
                found = True
                break
        if found:
            return True
        else:
            print(f"{creator} is NOT in {name}")
            return False

    def generate_dungeon(self, template_name, entry_room_key=None, creator=None, connecting_room=None):
        """
        Generate a dungeon based on the given template name.
        """
        template = DUNGEON_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"No dungeon template named {template_name}")

        # Use the first room's key as entry_room_key if not explicitly provided
        if not entry_room_key:
            entry_room_key = template["rooms"][0]["key"]

        # Create dungeon rooms and track them
        dungeon_rooms = {}
        for room_num in range(0, len(template["rooms"])):
            room_data = template["rooms"][room_num]
            
            room_class = "world.rooms.rooms.SUEntryRoom" if "sub_dungeon" in room_data else "world.rooms.rooms.SUDungeonRoom"
            # Using key=0 to force key to be the DB identifier, this will help later
            room = create_object(room_class, key=0)
            room.db.desc = room_data["desc"]
            room.name = room_data["key"]
            # I think you need something flagging the room as the entry room
            # Something like flagging on the first room created (assuming it's the entry room)
            if "start" in room_data:
                room.db.start = room_data["start"]

            if "sub_dungeon" in room_data:
                room.db.sub_dungeon = room_data["sub_dungeon"]
            
            dungeon_rooms[room_num] = room

        # Create exits
        for exit in template["exits"]:
            for room in range(0, len(dungeon_rooms)):
                if dungeon_rooms[room].name == exit["from"]:
                    from_room = dungeon_rooms[room]
                elif dungeon_rooms[room].name == exit["to"]:
                    to_room = dungeon_rooms[room]

            create_object("world.rooms.suexits.SUExit",
                          key=exit["key"],
                          aliases=exit.get("aliases1"),
                          location=from_room,
                          destination=to_room)
            
            if exit.get("two_way"):
                reverse_key = exit.get("reverse_key", "back")
                create_object("world.rooms.suexits.SUExit",
                              key=reverse_key,
                              aliases=exit.get("aliases2"),
                              location=to_room,
                              destination=from_room)


        # Might need an extra key-value pair to determine what is a sub dungeon entry, hard-coded for now
        if connecting_room:
            sub_dungeon_entry = dungeon_rooms[0]
            create_object("world.rooms.suexits.SUExit",
                          key="portal",
                          aliases="p",
                          location=connecting_room,
                          destination=sub_dungeon_entry)
            create_object("world.rooms.suexits.SUExit",
                          key="portal",
                          aliases="p",
                          location=sub_dungeon_entry,
                          destination=connecting_room)
    
        dungeon = create_object(key=dungeon_rooms[0].key)
        
        dungeon.db.dungeon_attributes = {
            "rooms" : dungeon_rooms,
            "entry_room": dungeon_rooms[0].name,
            "template_name" : template_name,
            "creator" : creator,
            "dungeon_num" : dungeon_rooms[0].key,
            "start_time" : time.time(),
        }
        character = ObjectDB.objects.get(db_key=creator)
        if template_name not in character.db.completed_dungeons:
            character.db.completed_dungeons.append(template_name)
        self.db.active_dungeons[dungeon.db.dungeon_attributes["dungeon_num"]] = dungeon

    def get_dungeon_key(self, identifier):
        """
        Retrieve a dungeon by identifier.

        Args:
            identifier (str): The identifier of the dungeon.

        Returns:
            key: The dungeon key
        """
        active_dungeons = self.db.active_dungeons
        for dungeon in active_dungeons:
            if active_dungeons[dungeon].dbref == identifier:
                return identifier
        
        #keys = self.db.active_dungeons.keys()
        #for key in keys:
        #    if key == identifier:
        #        return key
        
        return None

    def check_dungeon(self, creator, template):
        # Bool, Check if the creator already has this dungeon loaded. 
        # No dungeon loaded, continue = True
        # Dungeon already loaded, stop = False
        active_dungeons = self.db.active_dungeons
        found = False
        if not active_dungeons:
            return True
        for dungeon in active_dungeons:
            dungeon_creator = active_dungeons[dungeon].db.dungeon_attributes["creator"]
            dungeon_template_name = active_dungeons[dungeon].db.dungeon_attributes["template_name"]
            
            if creator == dungeon_creator and template == dungeon_template_name:
                found = True
                break               
        if found:
            return False
        else:
            return True

    def delete_dungeon(self, identifier):
        # Deletes the dungeon.
        result = search_object(identifier)
        obj = result[0]
        attr = obj.attributes.get("dungeon_attributes")["rooms"]
        name = obj.attributes.get("dungeon_attributes")["entry_room"]

        if attr:
            for attrs in attr.items():
                attrs[1].delete()
        
        obj.delete()
        del self.db.active_dungeons[name]

    def get_templates(self):
        """
        Returns a list of all available dungeon template keys in DUNGEON_TEMPLATES.
        
        Returns:
            list: A list of dungeon template names (keys) in DUNGEON_TEMPLATES.
        """
        return list(DUNGEON_TEMPLATES.keys())
    
DUNGEON_TEMPLATES = {
    "main_dungeon": {
        "description": "A mysterious main dungeon with an entry to a deeper sub-dungeon.",
        "rooms": [
            {"key": "Main Entrance", "desc": "The entrance to the main dungeon.", "start": True},
            {"key": "Sub-Dungeon Gateway", "desc": "A room with a glowing portal leading to a deeper dungeon.", "sub_dungeon": "sub_dungeon"},
        ],
        "exits": [
            {"from": "Main Entrance", "to": "Sub-Dungeon Gateway", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
        ],
    },
    "sub_dungeon": {
        "description": "A darker and more dangerous sub-dungeon.",
        "rooms": [
            {"key": "Sub-Dungeon Entrance", "desc": "The entrance to the sub-dungeon, lit by faint blue light.", "start": True},
            {"key": "Deep Chamber", "desc": "A dark, damp chamber with ancient carvings on the walls.", "sub_dungeon": "start_1_1"},
        ],
        "exits": [
            {"from": "Sub-Dungeon Entrance", "to": "Deep Chamber", "key": "east", "aliases1": "e", "reverse_key": "west", "aliases2": "w", "two_way": True},
        ],
    },
    "start_1_1": {
        "description": "A vast, mysterious dungeon with a gateway to a deeper realm.",
        "rooms": [
            {"key": "Ancient Hallway", "desc": "An old hallway with flickering torchlight.", "start": True},
            {"key": "Hall of Murals", "desc": "Intricate murals depicting battles long past cover the walls."},
            {"key": "Crystal Atrium", "desc": "A large atrium filled with glowing crystals."},
            {"key": "Forgotten Chapel", "desc": "An abandoned chapel with broken pews and shattered windows."},
            {"key": "Sunken Storage", "desc": "A storage room partially flooded with murky water."},
            {"key": "Iron Vault", "desc": "A secure vault with a heavy iron door."},
            {"key": "Shadowed Corridor", "desc": "A dimly lit corridor with shadows that seem to move."},
            {"key": "Looming Archway", "desc": "An imposing archway leading to another part of the dungeon."},
            {"key": "Sub-Dungeon Gateway", "desc": "A glowing portal hums softly, leading to a deeper dungeon.", "sub_dungeon": "start_1_2"},
            {"key": "Hidden Cellar", "desc": "A small cellar hidden beneath a trapdoor, holding secrets of the past."},
        ],
        "exits": [
            {"from": "Ancient Hallway", "to": "Hall of Murals", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
            {"from": "Hall of Murals", "to": "Crystal Atrium", "key": "east", "aliases1": "e", "reverse_key": "west", "aliases2": "w", "two_way": True},
            {"from": "Crystal Atrium", "to": "Forgotten Chapel", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
            {"from": "Forgotten Chapel", "to": "Sunken Storage", "key": "west", "aliases1": "w", "reverse_key": "east", "aliases2": "e", "two_way": True},
            {"from": "Sunken Storage", "to": "Iron Vault", "key": "south", "aliases1": "s", "reverse_key": "north", "aliases2": "n", "two_way": True},
            {"from": "Iron Vault", "to": "Shadowed Corridor", "key": "east", "aliases1": "e", "reverse_key": "west", "aliases2": "w", "two_way": True},
            {"from": "Shadowed Corridor", "to": "Looming Archway", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
            {"from": "Looming Archway", "to": "Sub-Dungeon Gateway", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
            {"from": "Sub-Dungeon Gateway", "to": "Hidden Cellar", "key": "east", "aliases1": "e", "reverse_key": "west", "aliases2": "w", "two_way": True},
        ],
    },
    "start_1_2": {
        "description": "A treacherous sub-dungeon filled with ancient traps and secrets.",
        "rooms": [
            {"key": "Portal Landing", "desc": "The glowing portal deposits you in this dimly lit chamber.", "start": True},
            {"key": "Jagged Cavern", "desc": "Sharp rocks jut out from the floor and walls."},
            {"key": "Warden's Quarters", "desc": "A small room with remnants of a long-forgotten warden."},
            {"key": "Collapsed Tunnel", "desc": "Rubble blocks part of this passage, but a narrow way remains."},
            {"key": "Glowstone Chamber", "desc": "Glowing stones illuminate this room with an eerie light."},
            {"key": "Ancient Fountain", "desc": "A fountain filled with crystal-clear water, despite the age of the dungeon."},
            {"key": "Gilded Treasury", "desc": "Ornate chests and piles of gold line the walls."},
            {"key": "Rune-Encrusted Hall", "desc": "Ancient runes cover every surface, faintly glowing."},
        ],
        "exits": [
            {"from": "Portal Landing", "to": "Jagged Cavern", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
            {"from": "Jagged Cavern", "to": "Warden's Quarters", "key": "east", "aliases1": "e", "reverse_key": "west", "aliases2": "w", "two_way": True},
            {"from": "Warden's Quarters", "to": "Collapsed Tunnel", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
            {"from": "Collapsed Tunnel", "to": "Glowstone Chamber", "key": "west", "aliases1": "w", "reverse_key": "east", "aliases2": "e", "two_way": True},
            {"from": "Glowstone Chamber", "to": "Ancient Fountain", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
            {"from": "Ancient Fountain", "to": "Gilded Treasury", "key": "east", "aliases1": "e", "reverse_key": "west", "aliases2": "w", "two_way": True},
            {"from": "Gilded Treasury", "to": "Rune-Encrusted Hall", "key": "north", "aliases1": "n", "reverse_key": "south", "aliases2": "s", "two_way": True},
        ],
    },
}

