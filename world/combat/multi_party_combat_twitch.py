from evennia import AttributeProperty, CmdSet, default_cmds
from evennia.commands.command import Command, InterruptCommand
from evennia.utils.utils import (
    display_len,
    inherits_from,
    list_to_string,
    pad,
    repeat,
    unrepeat,
)

import time

from world.character.characters import SUCharacter
from world.character.npc import SUMob
from world.combat.combat_base import (
    CombatActionAttack,
    CombatActionHold,
    CombatActionStunt,
    CombatActionUseItem,
    CombatActionWield,
    SUCombatBaseHandler,
)
from world.utils.enums import ABILITY_REVERSE_MAP

class SUCombatTwitchHandler(SUCombatBaseHandler):
    """
    This handler manages a shared combat context for multi-party, Twitch-style combat.
    It tracks multiple combatants and enables simultaneous action execution.
    """
    # fixed properties
    action_classes = {
        "hold": CombatActionHold,
        "attack": CombatActionAttack,
        "stunt": CombatActionStunt,
        "use": CombatActionUseItem,
        "wield": CombatActionWield,
    }
    # dynamic properties
    advantage_against = AttributeProperty(dict)
    disadvantage_against = AttributeProperty(dict)
    action_dict = AttributeProperty(dict)
    fallback_action_dict = AttributeProperty({"key": "attack", "dt": 3, "repeat": True})

    def at_script_creation(self):
        """
        Called once, when the combat handler is created.
        """
        # Store a list of all combatants in the shared combat context
        self.db.combatants = []
        self.db.action_queue = []
        self.current_ticker_ref = None

    def msg(self, message, broadcast=True, **kwargs):
        """
        Central place for sending messages to combatants. This allows
        for adding any combat-specific text-decoration in one place.

        Args:
            message (str): The message to send.
            combatant (Object): The 'You' in the message, if any.
            broadcast (bool): If `False`, `combatant` must be included and
                will be the only one to see the message. If `True`, send to
                everyone in the location.
            location (Object, optional): If given, use this as the location to
                send broadcast messages to. If not, use `self.obj` as that
                location.

        Notes:
            If `combatant` is given, use `$You/you()` markup to create
            a message that looks different depending on who sees it. Use
            `$You(combatant_key)` to refer to other combatants.
        """
        super().msg(message, combatant=self.obj, broadcast=broadcast, location=self.obj.location)

    def at_init(self):
        self.obj.cmdset.add(TwitchLookCmdSet, persistent=False)

    def display_combatants(self):
        """
        Display a list of current combatants to all participants in the combat.
        """
        if not self.db.combatants:
            return  # No combatants to display

        combatant_names = [combatant.key for combatant in self.db.combatants]
        combatant_list = ", ".join(combatant_names)

        # Broadcast the list of combatants to everyone in combat
        message = f"The following combatants are engaged in combat: {combatant_list}"
        for combatant in self.db.combatants:
            combatant.msg(message)

    def add_combatant(self, combatant):
        """
        Add a new combatant to the combat handler.
        Args:
            combatant (Object): A combatant (player or NPC) to add.
        """
        #self.msg(f"add_combattant: {combatant}")
        if combatant not in self.db.combatants:
            self.db.combatants.append(combatant)
            combatant.ndb.combathandler = self
            combatant.msg(f"You join combat!")
        # Display the current list of combatants
        #self.display_combatants()

    def get_sides(self, combatant):
        """
        Get a listing of the two 'sides' of this combat, from the perspective of the provided
        combatant. The sides don't need to be balanced.

        Args:
            combatant (Character or NPC): The one whose sides are to determined.

        Returns:
            tuple: A tuple of lists `(allies, enemies)`, from the perspective of `combatant`.
                Note that combatant itself is not included in either of these.

        """
        # get all entities involved in combat by looking up their combathandlers
        combatants = self.db.combatants 
        location = self.obj.location

        if hasattr(location, "allow_pvp") and location.allow_pvp:
            # in pvp, everyone else is an enemy
            allies = [combatant]
            enemies = [comb for comb in combatants if comb != combatant]
        else:
            # otherwise, enemies/allies depend on who combatant is
            pcs = [comb for comb in combatants if inherits_from(comb, SUCharacter)]
            npcs = [comb for comb in combatants if comb not in pcs]

            if combatant in pcs:
                # combatant is a PC, so NPCs are all enemies
                allies = pcs
                enemies = npcs
            else:
                # combatant is an NPC, so PCs are all enemies
                allies = npcs
                enemies = pcs
        #print(combatant,": allies:", allies, "enemies:", enemies)
        return allies, enemies

    def give_advantage(self, recipient, target):
        """
        Let a benefiter gain advantage against the target.

        Args:
            recipient (Character or NPC): The one to gain the advantage. This may or may not
                be the same entity that creates the advantage in the first place.
            target (Character or NPC): The one against which the target gains advantage. This
                could (in principle) be the same as the benefiter (e.g. gaining advantage on
                some future boost)

        """
        self.advantage_against[target] = True

    def give_disadvantage(self, recipient, target):
        """
        Let an affected party gain disadvantage against a target.

        Args:
            recipient (Character or NPC): The one to get the disadvantage.
            target (Character or NPC): The one against which the target gains disadvantage, usually
                an enemy.

        """
        self.disadvantage_against[target] = True

    def has_advantage(self, combatant, target):
        """
        Check if a given combatant has advantage against a target.

        Args:
            combatant (Character or NPC): The one to check if they have advantage
            target (Character or NPC): The target to check advantage against.

        """
        return self.advantage_against.get(target, False)

    def has_disadvantage(self, combatant, target):
        """
        Check if a given combatant has disadvantage against a target.

        Args:
            combatant (Character or NPC): The one to check if they have disadvantage
            target (Character or NPC): The target to check disadvantage against.

        """
        return self.disadvantage_against.get(target, False)

    def at_repeat(self):
        self.process_queue()

    def queue_action(self, action_dict, combatant):
        """
        Queue an action for the given combatant in the shared action queue.
        Args:
            action_dict (dict): A dictionary describing the action to queue.
            combatant (Object): The combatant queuing the action.
        """
        if not combatant in self.db.combatants:
            print(f"{combatant} is not part of {self.db.combatants}")
            return

        # Ensure action_dict has a valid 'key'
        action_key = action_dict.get("key", None)

        if not action_key:
            print(f"Action dictionary for {self.name} is missing a 'key'.")
            return

        if action_key not in self.action_classes:
            combatant.msg(f"{action_key} is not a valid action!")
            return

        # Handle the delay (dt) if it exists in the action dict
        dt = action_dict.get("dt", 0)  # Default to 0 delay if not provided
        time_to_act = time.time() + dt  # Current time + delay

        # Add the action to the shared queue
        self.db.action_queue.append({
            "combatant": combatant,
            "action_dict": action_dict,
            "time_to_act": time_to_act
        })

        # Sort the queue by time_to_act to ensure the soonest actions are executed first
        self.db.action_queue.sort(key=lambda x: x["time_to_act"])
        '''
        # If delay > 0, schedule the next action using at_repeat
        if dt > 0:
            print(f"Scheduling process_queue in {dt} seconds.")
            self.at_start(interval=dt, repeats=1, callback=self.process_queue)
        else:
            self.process_queue()
        '''

    def process_queue(self):
        """
        Periodically process the action queue to execute actions whose delay has expired.
        """
    
        print("Processing queue...")
        current_time = time.time()
        if not self.db.action_queue:
            return
        
        print(f"Processing action queue at {current_time}. Current queue: {self.db.action_queue}")

        # Iterate over the queue and execute actions whose time_to_act has passed
        while self.db.action_queue and self.db.action_queue[0]["time_to_act"] <= current_time:
            next_action = self.db.action_queue.pop(0)
            combatant = next_action["combatant"]
            action_dict = next_action["action_dict"]

            print(f"Executing action '{action_dict['key']}' for combatant '{combatant.key}'.")
            
            # Execute the action
            self.execute_next_action(action_dict, combatant)
        '''
        # If there are still actions in the queue, re-schedule the next one based on the next dt
        if self.db.action_queue:
            next_action_dict = self.db.action_queue[0]
            dt = max(0, next_action_dict["time_to_act"] - time.time())  # Calculate remaining delay time
            next_dt = max(0, next_action_dict["time_to_act"] - time.time())
            print(f"Rescheduling process_queue in {next_dt} seconds.")
            self.at_repeat(interval=next_dt, repeats=1, callback=self.process_queue)
        '''

    def execute_next_action(self, action_dict, combatant):
        """
        Execute the next action in the action queue.
        """
        action_key = action_dict["key"]
        action_class = self.action_classes.get(action_key)

        if action_class:
            action = action_class(self, combatant, action_dict)

            # Execute the action
            if action.can_use():
                action.execute()
                action.post_execute()
                print(f"Executed action '{action_dict['key']}' for combatant '{combatant.key}'.")
            else:
                combatant.msg(f"Action {action_dict['key']} cannot be used right now.")
        else:
            print(f"{combatant}: Unknown action '{action_dict['key']}'.")
        # Re-queue the action if it is set to repeat
        if action_dict.get("repeat", True):
            print(f"Re-queuing action '{action_dict['key']}' for combatant '{combatant.key}'.")
            self.action_dict = action_dict
            self.queue_action(self.action_dict, combatant)
        else:
            self.action_dict = self.fallback_action_dict
            self.queue_action(self.action_dict, combatant)

        # Check if combat should continue
        self.check_stop_combat()

    def check_stop_combat(self):
        """
        Determine if combat should end based on the state of combatants.
        """
        # Filter combatants to see if there are remaining active members on each side
        allies, enemies = self.get_sides(self.obj)

        location = self.obj.location
        
        # only keep combatants that are alive and still in the same room
        allies = [comb for comb in allies if comb.hp > 0 and comb.location == location]
        enemies = [comb for comb in enemies if comb.hp > 0 and comb.location == location]

        if not allies and not enemies:
            self.msg("Noone stands after the dust settles.", broadcast=False)
            self.stop_combat()
            return

        if not allies or not enemies:
            if allies + enemies == [self.obj]:
                self.msg("The combat is over.")
            else:
                still_standing = list_to_string(f"$You({comb.key})" for comb in allies + enemies)
                self.msg(
                    f"The combat is over. Still standing: {still_standing}.",
                    broadcast=False,
                )
            self.stop_combat()

    def stop_combat(self):
        """
        Stop the combat and clean up.
        """
        self.msg("Combat has ended for all combatants.")
        for combatant in self.db.combatants:
            combatant.msg("You have left combat.")
            del combatant.ndb.combathandler  # Remove reference to the combat handler
        self.db.combatants.clear()
        self.db.action_queue.clear()
        self.obj.cmdset.remove(TwitchLookCmdSet)
        self.delete()

class _BaseTwitchCombatCommand(Command):
    """
    Parent class for all twitch-combat commnads.

    """

    def at_pre_command(self):
        """
        Called before parsing.

        """
        if not self.caller.location or not self.caller.location.allow_combat:
            self.msg("Can't fight here!")
            raise InterruptCommand()

    def parse(self):
        """
        Handle parsing of most supported combat syntaxes (except stunts).

        <action> [<target>|<item>]
        or
        <action> <item> [on] <target>

        Use 'on' to differentiate if names/items have spaces in the name.

        """
        self.args = args = self.args.strip()
        self.lhs, self.rhs = "", ""

        if not args:
            return

        if " on " in args:
            lhs, rhs = args.split(" on ", 1)
        else:
            lhs, *rhs = args.split(None, 1)
            rhs = " ".join(rhs)
        self.lhs, self.rhs = lhs.strip(), rhs.strip()

    def get_or_create_combathandler(self, target=None):
        """
        Get or create the combathandler assigned to this combatant.

        """
        # If `self.caller` doesn't exist (for NPCs, etc.), fall back to `self`
        combatant = getattr(self, 'caller', self)        
        #target = self.caller.search(self.lhs)
        combathandler_key=f"{combatant.name}_twitch_combathandler"
        
        if not target:
            combatant.msg("You can't find that target.")
            raise InterruptCommand()
        # Check if the target is a character
        if not isinstance(target, (SUCharacter, SUMob)):
            combatant.msg(f"{target.key} is not a valid target. You can only attack monsters or other characters.")
            raise InterruptCommand()

        return SUCombatTwitchHandler.get_or_create_combathandler(
                obj=combatant,
                target=target, 
                key=combathandler_key
            )

class CmdAttack(_BaseTwitchCombatCommand):
    """
    Attack a target. Will keep attacking the target until
    combat ends or another combat action is taken.

    Usage:
        attack/hit <target>

    """

    key = "attack"
    aliases = ["hit"]
    help_category = "combat"

    def func(self):
        target = self.caller.search(self.lhs)
        if not target:
            return

        # Get or create a shared combat handler for this combat
        combathandler = self.get_or_create_combathandler(target=target)
        
        # Add the caller (the player or NPC initiating combat) and the target to the combat handler
        combathandler.add_combatant(self.caller)
        combathandler.add_combatant(target)
        
        # we use a fixed dt of 1 here, to mimic Diku style; one could also picture
        # attacking at a different rate, depending on skills/weapon etc.
        # Would need to call on the stats of the caller to determine dt of attack. 
        
        combathandler.queue_action({"key": "attack", "target": target, "dt": 1, "repeat": True}, self.caller)
        combathandler.msg(f"$You() $conj(attack) $You({target})!", self.caller)

class CmdUseItem(_BaseTwitchCombatCommand):
    """
    Use an item in combat. The item must be in your inventory to use.

    Usage:
        use <item>
        use <item> [on] <target>

    Examples:
        use potion
        use throwing knife on goblin
        use bomb goblin

    """

    key = "use"
    help_category = "combat"

    def parse(self):
        super().parse()

        if not self.args:
            self.msg("What do you want to use?")
            raise InterruptCommand()

        self.item = self.lhs
        self.target = self.rhs or "me"

    def func(self):
        item = self.caller.search(
            self.item, candidates=self.caller.equipment.get_usable_objects_from_backpack()
        )
        if not item:
            self.msg("(You must carry the item to use it.)")
            return
        if self.target:
            target = self.caller.search(self.target)
            if not target:
                return

        combathandler = self.get_or_create_combathandler(target)
        combathandler.queue_action({"key": "use", "item": item, "target": target, "dt": 3})
        combathandler.msg(
            f"$You() prepare to use {item.get_display_name(self.caller)}!", self.caller
        )

class CmdWield(_BaseTwitchCombatCommand):
    """
    Wield a weapon or spell-rune. You will the wield the item, swapping with any other item(s) you
    were wielded before.

    Usage:
      wield <weapon or spell>

    Examples:
      wield sword
      wield shield
      wield fireball

    Note that wielding a shield will not replace the sword in your hand, while wielding a two-handed
    weapon (or a spell-rune) will take two hands and swap out what you were carrying.

    """

    key = "wield"
    help_category = "combat"

    def parse(self):
        if not self.args:
            self.msg("What do you want to wield?")
            raise InterruptCommand()
        super().parse()

    def func(self):
        item = self.caller.search(
            self.args, candidates=self.caller.equipment.get_wieldable_objects_from_backpack()
        )
        if not item:
            self.msg("(You must carry the item to wield it.)")
            return
        combathandler = self.get_or_create_combathandler()
        combathandler.queue_action({"key": "wield", "item": item, "dt": 3})
        combathandler.msg(f"$You() reach for {item.get_display_name(self.caller)}!", self.caller)

class CmdLook(default_cmds.CmdLook, _BaseTwitchCombatCommand):
    
    def func(self):
        # get regular look, followed by a combat summary
        super().func()
        if not self.args:
            combathandler = self.get_or_create_combathandler(self.caller)
            txt = str(combathandler.get_combat_summary(self.caller))
            maxwidth = max(display_len(line) for line in txt.strip().split("\n"))
            self.msg(f"|r{pad(' Combat Status ', width=maxwidth, fillchar='-')}|n\n{txt}")

class TwitchCombatCmdSet(CmdSet):
    """
    Add to character, to be able to attack others in a twitch-style way.
    """

    key = "twitch_combat_cmdset"

    def at_cmdset_creation(self):
        self.add(CmdAttack())
        #self.add(CmdHold())
        #self.add(CmdStunt())
        #self.add(CmdUseItem())
        #self.add(CmdWield())

class TwitchLookCmdSet(CmdSet):
    """
    This will be added/removed dynamically when in combat.
    """

    key = "twitch_look_cmdset"

    def at_cmdset_creation(self):
        self.add(CmdLook())
