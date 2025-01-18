from evennia import CmdSet, InterruptCommand, default_cmds, search_object, create_script, search_script
from evennia.objects.models import ObjectDB
from evennia.utils.evmenu import EvMenu
from evennia.utils.utils import inherits_from
from commands.command import MuxCommand

from world.utils.enums import WieldLocation
from world.character.equipment import EquipmentError
from world.character.npc import SUTalkativeNPC, SUMob
from world.utils.utils import get_obj_stats
from world.character.characters import SUCharacter
from evennia.utils import evform, evtable
from evennia.contrib.rpg.health_bar import display_meter
import time

class CmdWieldOrWear(MuxCommand):
    """
    Wield a weapon/shield, or wear a piece of armor or a helmet.

    Usage:
      wield <item>
      wear <item>

    The item will automatically end up in the suitable spot, replacing whatever
    was there previously.

    """
    use_if_busy = False
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

class CmdRemove(MuxCommand):
    """
    Remove a remove a weapon/shield, armor or helmet.

    Usage:
      remove <item>
      unwield <item>
      unwear <item>

    To remove an item from the backpack, use |wdrop|n instead.

    """
    use_if_busy = False
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

class CmdGive(MuxCommand):
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
    use_if_busy = False
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

class CmdTalk(MuxCommand):
    """
    Start a conversations with shop keepers and other NPCs in the world.

    Args:
      talk <npc>

    """
    use_if_busy = False
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

class CmdScore(MuxCommand):
    """
    Score sheet for a character
    """
    use_if_busy = True
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
            xp = int(target.xp)
        else:
            account = "NPC"
            level = "N/A"
            xp = "N/A"

        # add data to each tagged form cell
        form.map(cells={1: target.name,
                        2: account,
                        3: "Something",
                        4: target.permissions,
                        5: level,
                        6: int(target.hp),
                        7: int(target.hp_max),
                        8: xp
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

class CmdRest(MuxCommand):
    """
    Start the resting script for the character.

    Usage:
        rest
    """
    key = "rest"

    def func(self):
        # Check if the caller is a character
        if not self.caller or not hasattr(self.caller, "db"):
            self.caller.msg("|rYou are not a valid target for resting.|n")
            return

        # Check if the healing script is already running
        if self.caller.scripts.has("healing_script") or self.caller.ndb.busy:
            self.caller.msg("|yYou are already resting.|n")
            return

        self.caller.ndb.busy = True
        self.caller.msg("|455Resting has started. You will gain HP periodically until fully healed.|n")
        # Start the healing script
        create_script("world.scripts.character_script.RestingScript", obj=self.caller)

class CmdLook(default_cmds.CmdLook):
    use_if_busy = False
    pass

class CmdInventory(MuxCommand):
    """
    View your inventory

    Usage:
      inventory

    """
    use_if_busy = False

    key = "inventory"
    aliases = ("i", "inv")

    def func(self):
        loadout = self.caller.equipment.display_loadout()
        backpack = self.caller.equipment.display_backpack()
        slot_usage = self.caller.equipment.display_slot_usage()

        self.caller.msg(f"{loadout}\n{backpack}\nYou use {slot_usage} equipment slots.")

class CmdRestore(MuxCommand):
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
                    SUCharacter.update_stats(puppet)
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
                SUCharacter.update_stats(target)
                self.caller.msg(f"{target.key}'s HP has been fully restored.")
            else:
                self.caller.msg(f"{target.key} does not have HP attributes to restore.")

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

class CmdParty(MuxCommand):
    """
    Party management and communication.

    Usage:
        party                    - Show party information.
        party create <name>      - Create a new party.
        party invite <character> - Invite a character to the party.
        party accept             - Accept a party invitation.
        party leave              - Leave the current party.
        party promote <member>   - Promote a member to leader.
        party remove <member>    - Remove a member from the party.
        party <message>          - Send a message to the party.

    """
    key = "party"
    locks = "cmd:all()"

    def func(self):
        
        # Show party status if no arguments are provided
        if not self.args.strip():
            status = display_party_status(self.caller)
            self.caller.msg(status)
            return

        args = self.args.strip().split(None, 1)

        if not args or not args[0]:
            self.display_party_status()
            return

        subcommand = args[0].lower()
        argument = args[1].strip() if len(args) > 1 else ""

        # Dispatch to the appropriate subcommand
        if subcommand == "create":
            self.party_create(argument)
        elif subcommand == "invite":
            self.party_invite(argument)
        elif subcommand == "accept":
            self.party_accept()
        elif subcommand == "leave":
            self.party_leave()
        elif subcommand == "remove":
            self.party_remove(argument)
        elif subcommand == "promote":
            self.party_promote(argument)
        elif subcommand == "disband":
            self.party_disband()
        else:
            # If no recognized subcommand, treat the input as a chat message
            self.party_chat(" ".join(args))

    # Subcommand implementations    
    def party_create(self, name):
        """Handle party creation."""
        if not name:
            self.caller.msg("You must specify a name for the party.")
            return

        if self.caller.db.party:
            self.caller.msg("You are already in a party. Leave your current party first.")
            return

        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return

        # Create a new party
        new_party = party_manager.create_party(self.caller, name)
        if not new_party:
            self.caller.msg(f"A party with the name '{name}' already exists.")
            return

        self.caller.db.party = name
        self.caller.msg(f"|gYou have created a new party named '{name}'.|n")

    def party_invite(self, target_name):
        """Handle inviting another character to the party."""
        if not target_name:
            self.caller.msg("You must specify someone to invite.")
            return

        target = self.caller.search(target_name)
        if not target:
            return

        if not self.caller.db.party:
            self.caller.msg("You are not in a party. Create one first.")
            self.caller.msg(f"Usage: party <create||invite|promote> [arguments]")
            return

        if target.db.party:
            self.caller.msg(f"{target.key} is already in a party.")
            return

        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return
        
        # Retrieve the party
        party_name = self.caller.db.party
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg("Your party no longer exists.")
            self.caller.db.party = None
            return
        
        # Check if the party is already full
        if len(party["member_ids"]) >= party_manager.MAX_PARTY_SIZE:
            self.caller.msg(f"|rThe party '{party_name}' is already full. Maximum size is {party_manager.MAX_PARTY_SIZE}.|n")
            return
        
        # Send an invitation
        target.db.party_invitation = self.caller.db.party
        self.caller.msg(f"You have invited {target.key} to your party.")
        target.msg(f"|gYou have been invited to join '{self.caller.db.party}' by {self.caller.key}.|n")

    def party_accept(self):
        """Handle accepting a party invitation."""
        if not self.caller.db.party_invitation:
            self.caller.msg("You have no pending party invitations.")
            return

        # Access the PartyManager script
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return
        
        # Resolve the party
        party_name = self.caller.db.party_invitation
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg(f"The party '{party_name}' no longer exists.")
            self.caller.db.party_invitation = None  # Clear the invitation
            return
        
        # Add the caller to the party
        self.caller.db.party_invitation = None  # Clear the invitation
        if party_manager.add_member_to_party(self.caller, party_name):
            self.caller.db.party = party_name
            self.caller.msg(f"|gYou have joined the party '{party_name}'.|n")

            # Notify the party members
            for member in party_manager.get_party_members(party_name):
                if member != self.caller:
                    member.msg(f"|g{self.caller.key} has joined the party.|n")

    def party_leave(self):
        """Handle leaving the party."""
        if not self.caller.db.party:
            self.caller.msg("You are not in a party.")
            self.caller.msg(f"Usage: party <create||invite|promote> [arguments]")
            return

        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return
        
        # Retrieve the party
        party_name = self.caller.db.party
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg("Your party no longer exists.")
            self.caller.db.party = None
            return
        # Remove the caller from the party
        self.caller.db.party = None
        
        if party["leader_id"] == self.caller.id and len(party["member_ids"]) > 1:
            # If the leader is leaving and there are remaining members
            remaining_members = [member for member in party["member_ids"] if member != self.caller.id]
            new_leader_id = remaining_members[0]  # Set the first member as the new leader
            new_leader = ObjectDB.objects.get(id=new_leader_id)  # Retrieve the new leader object
            party["leader_id"] = new_leader.id
            new_leader.msg(f"|yYou are now the leader of the party '{party['name']}'.|n")
        else:
            # If the character is not the leader, just remove them from the party
            if party_manager.remove_member_from_party(self.caller, party_name):
                self.caller.msg(f"You have left the party '{party_name}'.")
                remaining_members = party_manager.get_party_members(party_name)

        """Remove a character from the PartyManager's list of members."""
        if self.caller.id in party["member_ids"]:
            party["member_ids"].remove(self.caller.id)

        # Notify remaining members
        for member in remaining_members:
            #member = ObjectDB.objects.get(id=member_id)
            member.msg(f"|y{self.caller.key} has left the party.|n")

        # Disband the party if no members remain
        if not remaining_members:
            party_manager.remove_party(party_name)
            self.caller.msg(f"The party '{party_name}' has been disbanded.")

    def party_remove(self, target_name):
        """Handle removing a member from the party."""
        if not target_name:
            self.caller.msg("You must specify a party member to remove.")
            return

        if not self.caller.db.party:
            self.caller.msg("You are not in a party.")
            self.caller.msg(f"Usage: party <create||invite|promote> [arguments]")
            return

        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return

        # Retrieve the party
        party_name = self.caller.db.party
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg("Your party no longer exists.")
            return

         # Check if the caller is the leader
        if party["leader_id"] != self.caller.id:
            self.caller.msg("Only the party leader can remove members.")
            return

         # Find the target member
        target = next(
            (member for member in party_manager.get_party_members(party_name) if member.key.lower() == target_name.lower()),
            None,
        )
        if not target:
            self.caller.msg(f"{target_name} is not in your party.")
            return
        
        if party_manager.remove_member_from_party(target, party_name):
            target.db.party = None
            target.msg(f"|rYou have been removed from the party '{party_name}' by {self.caller.key}.|n")
            self.caller.msg(f"|yYou have removed {target.key} from the party.|n")

        # Notify remaining members
        for member in party_manager.get_party_members(party_name):
            member.msg(f"|y{target.key} has been removed from the party by {self.caller.key}.|n")

        # Disband the party if no members remain
        if not party_manager.get_party_members(party_name):
            party_manager.remove_party(party_name)
            self.caller.msg(f"The party '{party_name}' has been disbanded.")

    def party_promote(self, target_name):
        """Handle promoting a member to leader."""
        if not target_name:
            self.caller.msg("You must specify a party member to promote.")
            return

        if not self.caller.db.party:
            self.caller.msg("You are not in a party.")
            self.caller.msg(f"Usage: party <create||invite|promote> [arguments]")
            return

            # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return

        # Retrieve the party
        party_name = self.caller.db.party
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg("Your party no longer exists.")
            return

        # Check if the caller is the leader
        if party["leader_id"] != self.caller.id:
            self.caller.msg("Only the party leader can promote another member.")
            return

        # Find the target member
        target = next(
            (member for member in party_manager.get_party_members(party_name) if member.key.lower() == target_name.lower()),
            None,
        )
        if not target:
            self.caller.msg(f"{target_name} is not in your party.")
            return

        # Promote the target to leader
        party["leader_id"] = target.id
        self.caller.msg(f"|gYou have promoted {target.key} to the leader of the party.|n")
        target.msg(f"|gYou have been promoted to the leader of the party '{party_name}' by {self.caller.key}.|n")

        # Notify remaining members
        for member in party_manager.get_party_members(party_name):
            if member != target and member != self.caller:
                member.msg(f"|y{target.key} has been promoted to the leader of the party by {self.caller.key}.|n")

    def party_disband(self):
        """Handle disbanding a party."""
        if not self.caller.db.party:
            self.caller.msg("You are not in a party.")
            self.caller.msg(f"Usage: party <create||invite|promote> [arguments]")
            return

        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return
        
        # Retrieve the party
        party_name = self.caller.db.party
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg(f"The party '{party_name}' does not exist.")
            return

        # Check if the caller is the leader or has appropriate permissions
        if party["leader_id"] != self.caller.id:
            self.caller.msg("Only the party leader can disband the party.")
            return

        # Notify all members and disband the party
        members = party_manager.get_party_members(party_name)
        for member in members:
            member.msg(f"|rThe party '{party_name}' has been disbanded.|n")
            member.db.party = None

        # Remove the party from the PartyManager
        party_manager.remove_party(party_name)
        self.caller.msg(f"|gYou have disbanded the party '{party_name}'.|n")

    def party_chat(self, message):
        """
        Send a chat message to all members of the caller's party.
        """
        if not message:
            self.caller.msg("You must provide a message to send to your party.")
            return

        # Ensure the caller is in a party
        party_name = self.caller.db.party
        if not party_name:
            self.caller.msg("You are not in a party.")
            self.caller.msg(f"Usage: party <create||invite|promote> [arguments]")
            return

        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return

        # Retrieve the party
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg("Your party no longer exists.")
            return

        # Get all party members
        members = party_manager.get_party_members(party_name)

        # Send the message to all party members
        for member in members:
            member.msg(f"|c[Party] {self.caller.key}:|n {message}")

# Helper functions
def display_party_status(character):
    """
    Display the status of the party the character belongs to.

    Args:
        character (Object): The character whose party status to display.

    Returns:
        str: A formatted string containing the party status table.
    """
    party_name = character.db.party
    if not party_name:
        return "You are not in a party. \nUsage: party <create||invite|promote> [arguments]"

    # Access the PartyManager
    party_manager = search_script("party_manager").first()
    if not party_manager:
        return "Error: Party manager is not available."

    party = party_manager.get_party(party_name)
    if not party:
        return "Your party could not be found. It may have been disbanded."

    # Resolve party members
    member_ids = party["member_ids"]
    members = ObjectDB.objects.filter(id__in=member_ids)
    if not members:
        return f"The party '{party_name}' has no members."

    # Build the table (same as before)
    table = evtable.EvTable("|cMember|n", "|cHealth|n", "|cRole|n", border="cells")
    for member in members:
        if not member:
            continue
        hp = getattr(member, "hp", 0)
        hp_max = getattr(member, "hp_max", 100)
        health_meter = display_meter(hp, hp_max, length=20, show_values=True)
        role = "|yLeader|n" if member.id == party["leader_id"] else "|wMember|n"
        table.add_row(member.key, health_meter, role)

    return f"|cParty: {party_name}|n\n{str(table)}"

class CmdParties(MuxCommand):
    """
    Display a list of all active parties and their members, or disband a party.

    Usage:
        parties
        parties disband <party_name>
    """
    key = "parties"
    locks = "cmd:perm(Developer)"  # Only administrators or developers can use this


    def func(self):
        args = self.args.strip().split(None, 1)

        # Handle subcommands
        if args and args[0].lower() == "disband":
            party_name = args[1].strip() if len(args) > 1 else None
            self.disband_party(party_name)
            return

        # Default: Show active parties
        self.display_active_parties()

    def display_active_parties(self):
        """Display a list of all active parties."""
        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return

        # Retrieve all active parties
        parties = party_manager.db.parties
        if not parties:
            self.caller.msg("There are currently no active parties.")
            return

        # Prepare the table
        table = evtable.EvTable("|cParty Name|n", "|cLeader|n", "|cMembers|n", border="cells")

        for party_name, party_data in parties.items():
            # Get leader and members
            leader = self.resolve_object_by_id(party_data["leader_id"])
            members = [
                self.resolve_object_by_id(member_id)
                for member_id in party_data["member_ids"]
            ]

            # Format member names
            member_names = ", ".join(member.key for member in members if member)
            leader_name = leader.key if leader else "Unknown"

            # Add row to the table
            table.add_row(party_name, leader_name, member_names)

        # Display the table
        self.caller.msg("|cActive Parties:|n")
        self.caller.msg(str(table))

    def disband_party(self, party_name):
        """Handle disbanding a party."""
        if not party_name:
            self.caller.msg("You must specify the name of the party to disband.")
            return

        # Access the PartyManager
        party_manager = search_script("party_manager").first()
        if not party_manager:
            self.caller.msg("Error: Party manager is not available.")
            return

        # Retrieve the party
        party = party_manager.get_party(party_name)
        if not party:
            self.caller.msg(f"The party '{party_name}' does not exist.")
            return

        # Check if the caller is the leader or has appropriate permissions
        #if party["leader_id"] != self.caller.id and not self.caller.locks.check("perm", "Admin"):
        #    self.caller.msg("Only the party leader or an administrator can disband the party.")
        #    return

        # Notify all members and disband the party
        members = party_manager.get_party_members(party_name)
        for member in members:
            member.msg(f"|rThe party '{party_name}' has been disbanded.|n")
            member.db.party = None

        # Remove the party from the PartyManager
        party_manager.remove_party(party_name)
        self.caller.msg(f"|gYou have disbanded the party '{party_name}'.|n")

    def resolve_object_by_id(self, obj_id):
        """
        Resolve an object by its ID.

        Args:
            obj_id (int): The ID of the object.

        Returns:
            Object or None: The resolved object or None if not found.
        """
        return ObjectDB.objects.filter(id=obj_id).first()

class CmdListDungeons(MuxCommand):
    """
    List all active dungeons with their creators.

    Usage:
      dungeons
    """
    key = "dungeons"
    locks = "cmd:perm(Developer)"  # Only administrators or developers can use this

    def func(self):
        dungeon_manager = search_script("dungeon_manager").first()
        if not dungeon_manager:
            self.caller.msg("Dungeon Manager is not active.")
            return

        active_dungeons = dungeon_manager.db.active_dungeons
        current_time = time.time()
        if not active_dungeons:
            self.caller.msg("There are no active dungeons.")
            return

        # Create table
        table = evtable.EvTable("Number","Entry Room", "Name", "Creator", "Expire")
        # This loop is wrong. It iterates over the keys of the dictionary (ie. "rooms", "creator", "template_name"), which causes
        # the three repitions of the same data. This is not what we want. We want to iterate over the dungeons themselves.
        # You might need a second database entry to keep track of dungeons, with that db entry containing the current "active_dungeons" 
        
        for dungeon in active_dungeons:
            dungeon_number = active_dungeons[dungeon].dbref
            creator = active_dungeons[dungeon].db.dungeon_attributes["creator"]
            creator_name = creator if creator else "Unknown"
            template_name = active_dungeons[dungeon].db.dungeon_attributes["template_name"]
            entry_room = active_dungeons[dungeon].db.dungeon_attributes["entry_room"]
            start_time = active_dungeons[dungeon].db.dungeon_attributes["start_time"]
            elapsed = current_time - start_time
            expire = dungeon_manager.db.expire_time - elapsed
            table.add_row(dungeon_number, entry_room, template_name, creator_name, expire)

        #for dungeons in activedungeon_list_test:
            #first_room = 0 
            #creator = active_dungeons["creator"]
            #template_name = active_dungeons["template_name"]
            # Below should be a loop that finds the entry room and sets the entry room value accordingly.
            #first_room = active_dungeons["rooms"][0]["key"]
            
            #for rooms in active_dungeons["rooms"]:
             #   if "start" in rooms:
              #      first_room = rooms
            #self.caller.msg("0" + str(first_room))
            
            
            #self.caller.msg("2" + str(template_name))
            #self.caller.msg("3" + str(creator))

        #for dungeon_data in active_dungeons["rooms"]: #.items():
        #creator = active_dungeons["creator"]
        #creator_name = creator if creator else "Unknown"
        #template_name = active_dungeons["template_name"]
        #entry_room = active_dungeons["entry_room"]
        

        self.caller.msg(f"Active Dungeons:\n{table}")

class CmdDeleteDungeon(MuxCommand):

    key="dd"
    locks = "cmd:perm(Developer)"  # Only administrators or developers can use this


    def func(self):

        identifier = self.args.strip()
        self.dungeon_delete(identifier)   

    def dungeon_delete(self, identifier):

        """Handle deleting a dungeon."""
        if not identifier:
            self.caller.msg("You must specify the identifier of the dungeon to delete.")
            return

        # Access the DungeonManager
        dungeon_manager = search_script("dungeon_manager").first()
        if not dungeon_manager:
            self.caller.msg("Error: Dungeon manager is not available.")
            return

        # Retrieve the dungeon
        # Has to be fixed to delete none dungeons
        dungeon = dungeon_manager.get_dungeon_key(identifier)
        if not dungeon:
            self.caller.msg(f"The dungeon '{identifier}' does not exist.")
            return

        # Remove the dungeon from the DungeonManager
        dungeon_manager.delete_dungeon(identifier)
        self.caller.msg(f"|gYou have deleted the dungeon '{identifier}'.|n")

        


class SUCharacterCmdSet(CmdSet):
    """
    Groups all commands in one cmdset which can be added in one go to the DefaultCharacter cmdset.

    """
    key = "SUCharacter"

    def at_cmdset_creation(self):
        self.add(CmdWieldOrWear())
        self.add(CmdRemove())
        self.add(CmdGive())
        self.add(CmdTalk())
        self.add(CmdScore())
        self.add(CmdRest())
        self.add(CmdLook())
        self.add(CmdInventory())
        self.add(CmdRestore())
        self.add(CmdParty())
        self.add(CmdParties())
        self.add(CmdListDungeons())
        self.add(CmdDeleteDungeon())
