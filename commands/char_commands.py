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

        # add data to each tagged form cell
        form.map(cells={1: target.name,
                        2: target.account.name,
                        3: "Something",
                        4: target.permissions,
                        5: int(target.traits.level.value),
                        6: int(target.traits.lf.current),
                        7: int(target.traits.lf_base.value),
                        #8: int(target.stats.limit.value),
                        #9: int(target.stats.limit.max)
                        },
                        align="r")

        # create the EvTables
        tableA = evtable.EvTable("","Base","Mod","Total",
                            table=[["STR", "DEX", "INT"],
                            [int(target.stats.str_base.value), int(target.stats.dex_base.value), int(target.stats.int_base.value)],
                            [int(target.stats.str.mod), int(target.stats.dex.mod), int(target.stats.int.mod)],
                            [int(target.stats.str.value), int(target.stats.dex.value), int(target.stats.int.value)]],
                            border="incols")
        
        # add the tables to the proper ids in the form
        form.map(tables={"A": tableA })
        self.msg(str(form))
class CharCmdSet(CmdSet):

    def at_cmdset_creation(self):
        self.add(CmdHit)
        self.add(CmdScore)
        