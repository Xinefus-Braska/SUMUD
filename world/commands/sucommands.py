from evennia import CmdSet, Command, InterruptCommand, search_object
from evennia.utils.evmenu import EvMenu
from evennia.utils.utils import inherits_from

from world.utils.enums import WieldLocation
from world.character.equipment import EquipmentError
from world.character.npc import SUTalkativeNPC, SUMob
from world.utils.utils import get_obj_stats
from evennia.contrib.rpg.health_bar import display_meter
from world.character.characters import SUCharacter
from evennia.utils import evform, evtable

class SUCommand(Command):
    """
    Base SU command. This is on the form

        command <args>

    where whitespace around the argument(s) are stripped.

    """

    def parse(self):
        self.args = self.args.strip()
    
    def at_post_cmd(self):
        """
        Called after every command executed by the character.
        """
        super().at_post_cmd()
        if isinstance(self.caller, SUCharacter) and hasattr(self.caller, "update_prompt"):
            self.caller.update_prompt()

class CmdInventory(SUCommand):
    """
    View your inventory

    Usage:
      inventory

    """

    key = "inventory"
    aliases = ("i", "inv")

    def func(self):
        loadout = self.caller.equipment.display_loadout()
        backpack = self.caller.equipment.display_backpack()
        slot_usage = self.caller.equipment.display_slot_usage()

        self.caller.msg(f"{loadout}\n{backpack}\nYou use {slot_usage} equipment slots.")

class CmdWieldOrWear(SUCommand):
    """
    Wield a weapon/shield, or wear a piece of armor or a helmet.

    Usage:
      wield <item>
      wear <item>

    The item will automatically end up in the suitable spot, replacing whatever
    was there previously.

    """

    key = "wield"
    aliases = ("wear",)

    out_txts = {
        WieldLocation.BACKPACK: "You shuffle the position of {key} around in your backpack.",
        WieldLocation.TWO_HANDS: "You hold {key} with both hands.",
        WieldLocation.WEAPON_HAND: "You hold {key} in your strongest hand, ready for action.",
        WieldLocation.SHIELD_HAND: "You hold {key} in your off hand, ready to protect you.",
        WieldLocation.BODY: "You strap {key} on yourself.",
        WieldLocation.HEAD: "You put {key} on your head.",
    }

    def func(self):
        # find the item among those in equipment
        item = self.caller.search(self.args, candidates=self.caller.equipment.all(only_objs=True))
        if not item:
            # An 'item not found' error will already have been reported; we add another line
            # here for clarity.
            self.caller.msg("You must carry the item you want to wield or wear.")
            return

        use_slot = getattr(item, "inventory_use_slot", WieldLocation.BACKPACK)

        # check what is currently in this slot
        current = self.caller.equipment.slots[use_slot]

        if current == item:
            self.caller.msg(f"You are already using {item.key}.")
            return

        # move it to the right slot based on the type of object
        self.caller.equipment.move(item)

        # inform the user of the change (and potential swap)
        if current:
            self.caller.msg(f"Returning {current.key} to the backpack.")
        self.caller.msg(self.out_txts[use_slot].format(key=item.key))

class CmdRemove(SUCommand):
    """
    Remove a remove a weapon/shield, armor or helmet.

    Usage:
      remove <item>
      unwield <item>
      unwear <item>

    To remove an item from the backpack, use |wdrop|n instead.

    """

    key = "remove"
    aliases = ("unwield", "unwear")

    def func(self):
        caller = self.caller

        # find the item among those in equipment
        item = caller.search(self.args, candidates=caller.equipment.all(only_objs=True))
        if not item:
            # An 'item not found' error will already have been reported
            return

        current_slot = caller.equipment.get_current_slot(item)

        if current_slot is WieldLocation.BACKPACK:
            # we don't allow dropping this way since it may be unexepected by users who forgot just
            # where their item currently is.
            caller.msg(
                f"You already stashed away {item.key} in your backpack. Use 'drop' if "
                "you want to get rid of it."
            )
            return

        caller.equipment.remove(item)
        caller.equipment.add(item)
        caller.msg(f"You stash {item.key} in your backpack.")

# give / accept menu

def _rescind_gift(caller, raw_string, **kwargs):
    """
    Called when giver rescinds their gift in `node_give` below.
    It means they entered 'cancel' on the gift screen.

    """
    # kill the gift menu for the receiver immediately
    receiver = kwargs["receiver"]
    receiver.ndb._evmenu.close_menu()
    receiver.msg("The offer was rescinded.")
    return "node_end"

def node_give(caller, raw_string, **kwargs):
    """
    This will show to the giver until receiver accepts/declines. It allows them
    to rescind their offer.

    The `caller` here is the one giving the item. We also make sure to feed
    the 'item' and 'receiver' into the Evmenu.

    """
    item = kwargs["item"]
    receiver = kwargs["receiver"]
    text = f"""
        You are offering {item.key} to {receiver.get_display_name(looker=caller)}.
        |wWaiting for them to accept or reject the offer ...|n
        """.strip()

    options = {
        "key": ("cancel", "abort"),
        "desc": "Rescind your offer.",
        "goto": (_rescind_gift, kwargs),
    }
    return text, options

def _accept_or_reject_gift(caller, raw_string, **kwargs):
    """
    Called when receiver enters yes/no in `node_receive` below. We first need to
    figure out which.

    """
    item = kwargs["item"]
    giver = kwargs["giver"]
    if raw_string.lower() in ("yes", "y"):
        # they accepted - move the item!
        item = giver.equipment.remove(item)
        if item:
            try:
                # this will also add them to the equipment backpack, if possible
                item.move_to(caller, quiet=True, move_type="give")
            except EquipmentError:
                caller.location.msg_contents(
                    (
                        f"$You({giver.key.key}) $conj(try) to give "
                        f"{item.key} to $You({caller.key}), but they can't accept it since their "
                        "inventory is full."
                    ),
                    mapping={giver.key: giver, caller.key: caller},
                )
            else:
                caller.location.msg_contents(
                    (
                        f"$You({giver.key}) $conj(give) {item.key} to $You({caller.key}), "
                        "and they accepted the offer."
                    ),
                    mapping={giver.key: giver, caller.key: caller},
                )
        giver.ndb._evmenu.close_menu()
        return "node_end"

def node_receive(caller, raw_string, **kwargs):
    """
    Will show to the receiver and allow them to accept/decline the offer for
    as long as the giver didn't rescind it.

    The `caller` here is the one receiving the item. We also make sure to feed
    the 'item' and 'giver' into the EvMenu.

    """
    item = kwargs["item"]
    giver = kwargs["giver"]
    text = f"""
        {giver.get_display_name()} is offering you {item.key}:

        {get_obj_stats(item)}

        [Your inventory usage: {caller.equipment.display_slot_usage()}]
        |wDo you want to accept the given item? Y/[N]
        """
    options = ({"key": "_default", "goto": (_accept_or_reject_gift, kwargs)},)
    return text, options

def node_end(caller, raw_string, **kwargs):
    return "", None

class CmdGive(SUCommand):
    """
    Give item or money to another person. Items need to be accepted before
    they change hands. Money changes hands immediately with no wait.

    Usage:
      give <item> to <receiver>
      give <number of coins> [coins] to receiver

    If item name includes ' to ', surround it in quotes.

    Examples:
      give apple to ranger
      give "road to happiness" to sad ranger
      give 10 coins to ranger
      give 12 to ranger

    """

    key = "give"

    def parse(self):
        """
        Parsing is a little more complex for this command.

        """
        super().parse()
        args = self.args
        if " to " not in args:
            self.caller.msg(
                "Usage: give <item> to <recevier>. Specify e.g. '10 coins' to pay money. "
                "Use quotes around the item name it if includes the substring ' to '. "
            )
            raise InterruptCommand

        self.item_name = ""
        self.coins = 0

        # make sure we can use '...' to include items with ' to ' in the name
        if args.startswith('"') and args.count('"') > 1:
            end_ind = args[1:].index('"') + 1
            item_name = args[:end_ind]
            _, receiver_name = args.split(" to ", 1)
        elif args.startswith("'") and args.count("'") > 1:
            end_ind = args[1:].index("'") + 1
            item_name = args[:end_ind]
            _, receiver_name = args.split(" to ", 1)
        else:
            item_name, receiver_name = args.split(" to ", 1)

        # a coin count rather than a normal name
        if " coins" in item_name:
            item_name = item_name[:-6]
        if item_name.isnumeric():
            self.coins = max(0, int(item_name))

        self.item_name = item_name
        self.receiver_name = receiver_name

    def func(self):
        caller = self.caller

        receiver = caller.search(self.receiver_name)
        if not receiver:
            return

        # giving of coins is always accepted

        if self.coins:
            current_coins = caller.coins
            if self.coins > current_coins:
                caller.msg(f"You only have |y{current_coins}|n coins to give.")
                return
            # do transaction
            caller.coins -= self.coins
            receiver.coins += self.coins
            caller.location.msg_contents(
                f"$You() $conj(give) $You({receiver.key}) {self.coins} coins.",
                from_obj=caller,
                mapping={receiver.key: receiver},
            )
            return

        # giving of items require acceptance before it happens

        item = caller.search(self.item_name, candidates=caller.equipment.all(only_objs=True))
        if not item:
            return

        # testing hook
        if not item.at_pre_give(caller, receiver):
            return

        # before we start menus, we must check so either part is not already in a menu,
        # that would be annoying otherwise
        if receiver.ndb._evmenu:
            caller.msg(
                f"{receiver.get_display_name(looker=caller)} seems busy talking to someone else."
            )
            return
        if caller.ndb._evmenu:
            caller.msg("Close the current menu first.")
            return

        # this starts evmenus for both parties
        EvMenu(
            receiver, {"node_receive": node_receive, "node_end": node_end}, item=item, giver=caller
        )
        EvMenu(caller, {"node_give": node_give, "node_end": node_end}, item=item, receiver=receiver)

class CmdTalk(SUCommand):
    """
    Start a conversations with shop keepers and other NPCs in the world.

    Args:
      talk <npc>

    """

    key = "talk"

    def func(self):
        target = self.caller.search(self.args)
        if not target:
            return

        if not inherits_from(target, SUTalkativeNPC):
            self.caller.msg(
                f"{target.get_display_name(looker=self.caller)} does not seem very talkative."
            )
            return
        target.at_talk(self.caller)

class CmdScore(SUCommand):
    """
    Score sheet for a character
    """
    key = "score"
    aliases = "sc"

    def func(self):
        if self.caller.check_permstring("Developer"): 
            if self.args:
                # Use a global search to find the character (case-insensitive search by default)
                target_name = self.args.strip()
                potential_targets = search_object(target_name)
        
                # Narrow down to the first valid character target
                target = None
                for obj in potential_targets:
                    if isinstance(obj, (SUCharacter, SUMob)):
                        target = obj
                        break
                    elif not target:
                        self.caller.msg(f"Could not find a valid character or mob named '{target_name}'.")
                        return
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

class CmdDiagnose(Command):
        """
        see how hurt your are

        Usage: 
          diagnose [target]

        This will give an estimate of the target's health. Also
        the target's prompt will be updated. 
        """ 
        key = "diagnose"
        locks = "cmd:perm(Developer)"  # Only administrators or developers can use this
        
        def func(self):
            if not self.args:
                target = self.caller
            else:
                target = self.caller.search(self.args)
                if not target:
                    return
            # try to get health, mana and stamina
            hp = target.db.hp

            if hp is None:
                # Attributes not defined          
                self.caller.msg("Not a valid target!")
                return 
             
            text = f"You diagnose {target} as having {hp} health."
            healthbar = display_meter(target.db.hp,target.db.hp_max)
            self.caller.msg(text, prompt=healthbar)

class CmdDebug(Command):
    key = "debug"
    locks = "cmd:perm(Developer)"  # Only administrators or developers can use this

    def func(self):
        self.caller.msg("Debug command executed.")

class CmdRestore(Command):
    """
    Restore health for all puppets or a specific character/object.

    Usage:
        restore
        restore <target>

    Without arguments, restores all puppeted characters' HP to their maximum.
    With a target, restores the HP of the specified object/character.

    Note:
        This command can only be used by administrators.
    """

    key = "restore"
    locks = "cmd:perm(Developer)"  # Only administrators or developers can use this

    def func(self):
        """
        Command functionality.
        """
        if not self.args:
            # Restore all puppets
            puppets = [
                obj for obj in self.caller.location.contents
                if hasattr(obj, "account") and obj.account
            ]
            if not puppets:
                self.caller.msg("No puppeted characters found to restore.")
                return

            for puppet in puppets:
                if hasattr(puppet.db, "hp") and hasattr(puppet.db, "hp_max"):
                    puppet.db.hp = puppet.db.hp_max
                    puppet.msg("Your HP has been fully restored.")
            self.caller.msg("All puppeted characters have been restored to full HP.")
        else:
            # Restore a specific target
            target = self.caller.search(self.args.strip())
            if not target:
                self.caller.msg(f"Could not find a target named '{self.args.strip()}'.")
                return

            if hasattr(target.db, "hp") and hasattr(target.db, "hp_max"):
                target.db.hp = target.db.hp_max
                target.msg("Your HP has been fully restored.")
                self.caller.msg(f"{target.key}'s HP has been fully restored.")
            else:
                self.caller.msg(f"{target.key} does not have HP attributes to restore.")


class SUCharacterCmdSet(CmdSet):
    """
    Groups all commands in one cmdset which can be added in one go to the DefaultCharacter cmdset.

    """

    key = "SUCharacter"

    def at_cmdset_creation(self):
        self.add(CmdInventory())
        self.add(CmdWieldOrWear())
        self.add(CmdRemove())
        self.add(CmdGive())
        self.add(CmdTalk())
        self.add(CmdScore())

class SUAdminCmdSet(CmdSet):
    """
    Admin commands
    """

    key = "SUAdmin"

    def at_cmdset_creation(self):
        self.add(CmdDiagnose())
        self.add(CmdDebug())
        self.add(CmdRestore())