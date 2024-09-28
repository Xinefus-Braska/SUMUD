from evennia import Command
from evennia import CmdSet

class CmdLookWithMap(Command):
    """
    Overridden 'look' command that includes a map display.
    """

    key = "look"
    aliases = ["l"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        """
        This function executes when the 'look' command is called.
        """

        caller = self.caller
        location = caller.location

        if not location:
            caller.msg("You are nowhere.")
            return
        
        # Display the map by executing the 'map' command
        caller.execute_cmd("map")
        
        # Show the regular room description (default Evennia behavior)
        description = location.return_appearance(caller)
        caller.msg(description)


class MappingCmdSet(CmdSet):

    def at_cmdset_creation(self):
        self.add(CmdLookWithMap)
        # self.add(CmdMoveWithMap)
        # self.add(CmdNorthWithMap)