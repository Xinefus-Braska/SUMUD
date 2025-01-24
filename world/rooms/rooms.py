
from evennia.objects.objects import DefaultRoom

from copy import deepcopy

from evennia import AttributeProperty, DefaultCharacter, search_script
from evennia.utils.utils import inherits_from
from evennia.utils.evmenu import EvMenu
from world.character.random import GenerateMob

CHAR_SYMBOL = "|w@|n"
CHAR_ALT_SYMBOL = "|w>|n"
ROOM_SYMBOL = "|bo|n"
LINK_COLOR = "|B"

_MAP_GRID = [
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    [" ", " ", "@", " ", " "],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
]

_EXIT_GRID_SHIFT = {
    "north": (0, 1, "||"),
    "east": (1, 0, "-"),
    "south": (0, -1, "||"),
    "west": (-1, 0, "-"),
    "northeast": (1, 1, "/"),
    "southeast": (1, -1, "\\"),
    "southwest": (-1, -1, "/"),
    "northwest": (-1, 1, "\\"),
}

class SURoom(DefaultRoom):
    """
    Simple room supporting some SU-specifics.

    """

    allow_combat = AttributeProperty(False, autocreate=False)
    allow_pvp = AttributeProperty(False, autocreate=False)
    allow_death = AttributeProperty(False, autocreate=False)

    def format_appearance(self, appearance, looker, **kwargs):
        """Don't left-strip the appearance string"""
        return appearance.rstrip()

    def get_display_header(self, looker, **kwargs):
        """
        Display the current location as a mini-map.

        """
        # make sure to not show make a map for users of screenreaders.
        # for optimization we also don't show it to npcs/mobs
        if not inherits_from(looker, DefaultCharacter) or (
            looker.account and looker.account.uses_screenreader()
        ):
            return ""

        # build a map
        map_grid = deepcopy(_MAP_GRID)
        dx0, dy0 = 2, 2
        map_grid[dy0][dx0] = CHAR_SYMBOL
        for exi in self.exits:
            dx, dy, symbol = _EXIT_GRID_SHIFT.get(exi.key, (None, None, None))
            if symbol is None:
                # we have a non-cardinal direction to go to - indicate this
                map_grid[dy0][dx0] = CHAR_ALT_SYMBOL
                continue
            map_grid[dy0 + dy][dx0 + dx] = f"{LINK_COLOR}{symbol}|n"
            if exi.destination != self:
                map_grid[dy0 + dy + dy][dx0 + dx + dx] = ROOM_SYMBOL

        # Note that on the grid, dy is really going *downwards* (origo is
        # in the top left), so we need to reverse the order at the end to mirror it
        # vertically and have it come out right.
        return "  " + "\n  ".join("".join(line) for line in reversed(map_grid))

class SUEntryRoom(SURoom):
    """
    A room that triggers dungeon generation when a character enters it.
    """

    def at_object_receive(self, obj, source_location, **kwargs):
        """
        Called when an object (e.g., a character) enters this room.
        """
        if obj.has_account:  # Ensure the object is a player character
            sub_dungeon = self.db.sub_dungeon
            if sub_dungeon:
                # Get the DungeonManager script
                dungeon_manager = search_script("dungeon_manager").first()
                if dungeon_manager:
                    # Check if this dungeon is already loaded for the player
                    if dungeon_manager.check_dungeon(obj.name, sub_dungeon):
                        # Generate the sub-dungeon
                        dungeon_manager.generate_dungeon(
                            template_name=sub_dungeon,
                            creator=obj.name,
                            connecting_room=self,
                        )
                        obj.msg(f"You feel a magical pull as the {sub_dungeon} materializes before you.")
                        if sub_dungeon not in obj.db.completed_dungeons:
                            obj.db.completed_dungeons.append(sub_dungeon)
                else:
                    obj.msg("There seems to be a glitch... no DungeonManager found.")
            else:
                obj.msg("This room feels strange, but nothing happens.")
        super().at_object_receive(obj, source_location, **kwargs)

class SUPvPRoom(SURoom):
    """
    Room where PvP can happen, but noone gets killed.

    """

    allow_combat = AttributeProperty(True, autocreate=False)
    allow_pvp = AttributeProperty(True, autocreate=False)

    def get_display_footer(self, looker, **kwargs):
        """
        Customize footer of description.
        """
        return "|yNon-lethal PvP combat is allowed here!|n"

class SUHouse(SURoom):
    """
    Room where character logs in.

    """

    allow_combat = AttributeProperty(False, autocreate=False)
    allow_pvp = AttributeProperty(False, autocreate=False)

    def get_display_footer(self, looker, **kwargs):
        """
        Customize footer of description.
        """
        return "|yThis is a House.|n"

class SUArmoury(SURoom):
    """
    Room where character can access their stored items and currency.

    """

    allow_combat = AttributeProperty(False, autocreate=False)
    allow_pvp = AttributeProperty(False, autocreate=False)

    def get_display_footer(self, looker, **kwargs):
        """
        Customize footer of description.
        """
        return "|yThis is an Armoury.|n"

class SURift(SURoom):
    """
    Room where characters can access other areas.

    """

    allow_combat = AttributeProperty(False, autocreate=False)
    allow_pvp = AttributeProperty(False, autocreate=False)

    def get_display_footer(self, looker, **kwargs):
        """
        Customize footer of description.
        """
        return "|yThis is a Rift|n"

class SUDungeonRoom(SURoom):
    """
    Room that is part of a dungeon.

    """

    allow_combat = AttributeProperty(True, autocreate=False)
    allow_pvp = AttributeProperty(False, autocreate=False)
    allow_death = AttributeProperty(True, autocreate=False)

    def at_object_creation(self):
        """
        Set the `not_clear` tag on the room. This is removed when the room is
        'cleared', whatever that means for each room.

        We put this here rather than in the room-creation code so we can override
        easier (for example we may want an empty room which auto-clears).

        """
        self.tags.add("not_clear", category="dungeon_room")

    def clear_room(self):
        self.tags.remove("not_clear", category="dungeon_room")

    @property
    def is_room_clear(self):
        return not bool(self.tags.get("not_clear", category="dungeon_room"))

    def get_display_footer(self, looker, **kwargs):
        """
        Customize footer of description.
        """
        return "|rThis is a Dungeon Room.|n"
    
    def at_object_receive(self, obj, source_location, **kwargs):
        """
        Called when an object (e.g., a character) enters this room.
        First thing to happen when entering the room is to check if the room is clear. 
        """
        if obj.has_account:  # Ensure the object is a player character
            if not self.is_room_clear:
                # Generate the enemies for this room.
                #GenerateMob.generate_mob(self, obj)
                obj.msg("Here come the enemies!")
                # This will be a function to either generate mobs or not. 
                self.clear_room()


        super().at_object_receive(obj, source_location, **kwargs)