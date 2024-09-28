"""
Room

Rooms are simple containers that has no location of their own.

"""

from evennia.objects.objects import DefaultRoom

from .objects import ObjectParent


class Room(ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). They also use basetype_setup() to
    add locks so they cannot be puppeted or picked up.
    (to change that, use at_object_creation instead)

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Objects.
    """
    # appearance_template = '|c{name}{extra_name_info}\n|n{header}\n{desc}\n{exits}\n{characters}\n{things}\n{footer}\n'

    def get_display_header(self, looker, **kwargs):
        """
        Displays a minimap above the room description, if there is one.
        """
        looker.execute_cmd("map")
        return ""

    pass