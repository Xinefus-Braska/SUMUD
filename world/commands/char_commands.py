from commands.command import Command
from evennia import CmdSet
from evennia.utils import evform, evtable

# This is a super dumb basic hit command
class CmdHit(Command):
    """
    Hit a target.

    Usage:
      hit <target> [[with] <weapon>]

    """
    key = "hit"

    def parse(self):
        self.args = self.args.strip()
        target, *weapon = self.args.split(" with ", 1)
        if not weapon:
            target, *weapon = target.split(" ", 1)
        self.target = target.strip()
        if weapon:
            self.weapon = weapon[0].strip()
        else:
            self.weapon = ""

    def func(self):
        if not self.args:
            self.caller.msg("Who do you want to hit?")
            return
        # get the target for the hit
        target = self.caller.search(self.target)
        if not target:
            return
        # get and handle the weapon
        weapon = None
        if self.weapon:
            weapon = self.caller.search(self.weapon)
        if weapon:
            weaponstr = f"{weapon.key}"
        else:
            weaponstr = "bare fists"

        self.caller.msg(f"You hit {target.key} with {weaponstr}!")
        target.msg(f"You got hit by {self.caller.key} with {weaponstr}!")

class CmdScore(Command):
    """
    Score sheet for a character
    """
    key = "score"
    aliases = "sc"

    def func(self):
        if self.caller.check_permstring("Developer"): 
            if self.args:
                target = self.caller.search(self.args)
            else:
                target = self.caller    
        else:
            target = self.caller

        # create a new form from the template - using the python path
        form = evform.EvForm("world.forms.scoreform")
        if target.is_typeclass("world.character.characters.SUCharacter"):
            account = target.account.name
            level = int(target.level)
        else:
            account = "NPC"
            level = "N/A"

        # add data to each tagged form cell
        form.map(cells={1: target.name,
                        2: account,
                        3: "Something",
                        4: target.permissions,
                        5: level,
                        6: int(target.hp),
                        7: int(target.hp_max)
                        },
                        align="r")

        # create the EvTables
        tableA = evtable.EvTable("","Base","Mod","Total",
                            table=[["STR", "DEX", "INT"],
                            [int(target.strength), int(target.dexterity), int(target.intelligence)],
                            [5, 5, 5],
                            [5, 5, 5]],
                            border="incols")
        
        # add the tables to the proper ids in the form
        form.map(tables={"A": tableA })
        self.msg(str(form))

class CharCmdSet(CmdSet):

    def at_cmdset_creation(self):
        #self.add(CmdHit)
        self.add(CmdScore)
        