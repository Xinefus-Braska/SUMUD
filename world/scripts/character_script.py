from evennia import DefaultScript
from world.character.characters import SUCharacter

class RestingScript(DefaultScript):
    """
    A script that periodically restores HP for a character when they are resting until they are at full HP.
    """

    def at_script_creation(self):
        """
        Called when the script is first created.
        """
        self.key = "resting_script"
        self.interval = 10  # Run every 10 seconds
        self.persistent = True  # Make sure the script persists between reboots
        self.ndb.resting = False  # Track if the first interval has passed

    def at_repeat(self):
        """
        Called at every interval (10 seconds in this case).
        """
        character = self.obj

        # Ensure the character has hp and hp_max attributes
        if hasattr(character.db, "hp") and hasattr(character.db, "hp_max"):
            # Skip healing during the first interval
            if not self.ndb.resting:
                self.ndb.resting = True
                return
            
            if character.db.hp < character.db.hp_max:
                # Heal 1 HP per interval (customize as needed)
                character.db.hp += 1
                # Need to add function to update stats and eventually the prompt
                SUCharacter.update_stats(character)
                character.msg(f"|435As you meditate deeply on your life, you feel regenerated and restored.|n")

                # Prevent over-healing
                if character.db.hp >= character.db.hp_max:
                    character.db.hp = character.db.hp_max
                    character.msg("|gYou are fully healed.|n")
                    character.ndb.busy = False
                    self.delete()
            else:
                # Stop the script if HP is already full
                character.msg("|gYou are fully healed.|n")
                character.ndb.busy = False
                self.delete()
        else:
            # Stop the script if the character doesn't have hp attributes
            character.msg("|rError: Missing hp or hp_max attribute. The healing script has stopped.|n")
            character.ndb.busy = False
            self.delete()
