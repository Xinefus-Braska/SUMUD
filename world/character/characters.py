"""
Character class.

"""
from evennia.objects.objects import DefaultCharacter
from evennia.typeclasses.attributes import AttributeProperty
from evennia.utils.logger import log_trace
from evennia.utils.utils import lazy_property
from evennia.objects.models import ObjectDB

from world.utils.rules import dice
from world.character.equipment import EquipmentError, EquipmentHandler
from world.rooms.quests import SUQuestHandler
from evennia.contrib.rpg.health_bar import display_meter

class LivingMixin:

    # makes it easy for mobs to know to attack PCs
    is_pc = False  

    @property
    def hurt_level(self):
        """
        String describing how hurt this character is.
        """
        percent = max(0, min(100, 100 * (self.hp / self.hp_max)))
        if 95 < percent <= 100:
            return "|gPerfect|n"
        elif 80 < percent <= 95:
            return "|gScraped|n"
        elif 60 < percent <= 80:
            return "|GBruised|n"
        elif 45 < percent <= 60:
            return "|yHurt|n"
        elif 30 < percent <= 45:
            return "|yWounded|n"
        elif 15 < percent <= 30:
            return "|rBadly wounded|n"
        elif 1 < percent <= 15:
            return "|rBarely hanging on|n"
        elif percent == 0:
            return "|RCollapsed!|n"

    def heal(self, hp, healer=None): 
        """ 
        Heal hp amount of health, not allowing to exceed our max hp     
        """ 
        damage = self.hp_max - self.hp 
        healed = min(damage, hp) 
        self.hp += healed 
        
        if healer is self:
            self.msg(f"|gYou heal yourself for {healed} health.|n")
        elif healer:
            self.msg(f"|g{healer.key} heals you for {healed} health.|n")
        else:
            self.msg(f"You are healed for {healed} health.")
        
    def at_attacked(self, attacker, **kwargs):
        """
        Called when being attacked / combat starts.
        """
        from world.combat.multi_party_combat_twitch import _BaseTwitchCombatCommand as Twitch
        
        target = attacker
        # Get or create a shared combat handler for this combat
        combathandler = Twitch.get_or_create_combathandler(self, target=target)
        
        # Add the caller (the player or NPC initiating combat) and the target to the combat handler
        combathandler.add_combatant(self)
        combathandler.add_combatant(target)
        
        # we use a fixed dt of 3 here, to mimic Diku style; one could also picture
        # attacking at a different rate, depending on skills/weapon etc.
        combathandler.queue_action({"key": "attack", "target": target, "dt": 1, "repeat": False}, self)
        #combathandler.msg(f"$You() $conj(join) battle with $You({target.key})!", self)

    def at_damage(self, damage, attacker=None):
        """
        Called when attacked and taking damage.

        """
        self.hp -= damage

    def at_defeat(self):
        """
        Called when this living thing reaches HP 0.

        """
        # by default, defeat means death
        self.at_death()

    def at_death(self):
        """
        Called when this living thing dies.

        """
        self.location.msg_contents(
            "|r$You() $conj(collapse) in a heap.\nDeath embraces $You() ...|n",
            from_obj=self,
        )

    def at_pay(self, amount):
        """When paying coins, make sure to never detract more than we have"""
        amount = min(amount, self.coins)
        self.coins -= amount
        return amount
        
    def at_looted(self, looter):
        """Called when looted by another entity""" 
        # default to stealing some coins 
        loot = self.coins
        looter.coins += loot
        looter.msg(f"You loot {self.key} for {loot} coins.")

    def pre_loot(self, defeated_enemy):
        """
        Called just before looting an enemy.

        Args:
            defeated_enemy (Object): The enemy soon to loot.

        Returns:
            bool: If False, no looting is allowed.

        """
        return True

    def at_do_loot(self, defeated_enemy):
        """
        Called when looting another entity.

        Args:
            defeated_enemy: The thing to loot.

        """
        # loot the enemy
        if hasattr(defeated_enemy, "at_looted"):
            defeated_enemy.at_looted(self)
        else:
            print(f"DEBUG: {defeated_enemy.key} has no at_looted method.")
        self.post_loot(defeated_enemy)

    def post_loot(self, defeated_enemy):
        """
        Called just after having looted an enemy.

        Args:
            defeated_enemy (Object): The enemy just looted.

        """
        from world.character.npc import SUMob

        if hasattr(self, "is_pc") and self.is_pc:
            if SUCharacter.add_xp(self, int(SUMob.get_xp_value(defeated_enemy))):
                self.level_up("strength", "dexterity", "intelligence")

class SUCharacter(LivingMixin, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Object child classes like this.

    """
    is_pc = True
    prompt_on = True

    # these are the ability bonuses. Defense is always 10 higher
    strength = AttributeProperty(default=1)
    dexterity = AttributeProperty(default=1)
    constitution = AttributeProperty(default=1)
    intelligence = AttributeProperty(default=1)
    wisdom = AttributeProperty(default=1)
    charisma = AttributeProperty(default=1)

    hp = AttributeProperty(default=4)
    hp_max = AttributeProperty(default=4)
    level = AttributeProperty(default=1)
    coins = AttributeProperty(default=0)  # copper coins

    xp = AttributeProperty(default=0)
    xp_per_level = 1000

    @lazy_property
    def completed_dungeons(self):
        """
        Get a list of completed dungeons.
        """
        return self.db.completed_dungeons or []

    @lazy_property 
    def equipment(self):
        """Allows to access equipment like char.equipment.worn"""
        return EquipmentHandler(self)
    
    @lazy_property
    def quests(self):
        """Access and track quests"""
        return SUQuestHandler(self)

    @property
    def weapon(self):
        return self.equipment.weapon

    @property
    def armor(self):
        return self.equipment.armor

    def at_object_creation(self):
        """
        Called only when first created.

        """
        super().at_object_creation()
        self.db.party = None  # Reference to the party this character belongs to
        self.db.completed_dungeons = ["main_dungeon"]  # List of completed dungeons

    def at_pre_puppet(self, account, session=None):
        """
        Use this to set up their home room.
        """
        if not account.db.house:
            account.at_account_creation()

        # Get the account's shared rooms
        if not account.db.house == self.home:
                self.home = account.db.house  # Set the home to the account's house
                self.db.armoury = account.db.armoury  # Link to the Armory
                self.db.rift = account.db.rift  # Link to the Rift

        # Move the character to their home at every login
        self.location = self.home

        super().at_pre_puppet(account)  # Call the parent method

    def at_pre_unpuppet(self):
        """
        Hook called when the character disconnects (quits).
        """
        print(f"{self.key} has disconnected.")
        # Check if the character is part of a party
        party_name = self.db.party
        if not party_name:
            return  # Not in a party, nothing to do

        # Access the PartyManager
        from evennia import search_script
        party_manager = search_script("party_manager").first()
        if not party_manager:
            return  # PartyManager not available, can't handle disconnection

        # Retrieve the party
        party = party_manager.get_party(party_name)
        if not party:
            self.db.party = None  # Party doesn't exist, clear the reference
            return  # Party doesn't exist, nothing to do

        # Remove the character from the party
        self.db.party = None  # Clear party reference for the disconnected member

        if party["leader_id"] == self.id and len(party["member_ids"]) > 1:
            # If the leader is leaving and there are remaining members
            remaining_members = [member for member in party["member_ids"] if member != self.id]
            new_leader_id = remaining_members[0]  # Set the first member as the new leader
            new_leader = ObjectDB.objects.get(id=new_leader_id)  # Retrieve the new leader object
            party["leader_id"] = new_leader.id
            new_leader.msg(f"|yYou are now the leader of the party '{party['name']}'.|n")
        else:
            # If the character is not the leader, just remove them from the party
            if party_manager.remove_member_from_party(self, party_name):
                self.msg(f"You have left the party '{party_name}'.")
                remaining_members = party_manager.get_party_members(party_name)

        """Remove a character from the PartyManager's list of members."""
        if self.id in party["member_ids"]:
            party["member_ids"].remove(self.id)
            self.msg(f"You have left the party '{party_name}'.")
        
        # Notify remaining party members
        remaining_members = party_manager.get_party_members(party_name)
        for member in remaining_members:
            member.msg(f"|y{self.key} has left the party '{party_name}' due to disconnection.|n")

        # Disband the party if no members remain
        if not remaining_members:
            party_manager.remove_party(party_name)
            self.msg(f"The party '{party_name}' has been disbanded.")

       # Reassign leadership if the disconnecting member was the leader
        if party["leader_id"] == self.id:
            new_leader = remaining_members[0]
            party["leader_id"] = new_leader.id
            new_leader.msg(f"|yYou are now the leader of the party '{party_name}'.|n")

    def at_pre_move(self, destination, **kwargs):
        """
        Called by self.move_to when trying to move somewhere. If this returns
        False, the move is immediately cancelled.
        """
        """
        # check if we have any statuses that prevent us from moving
        if statuses := self.tags.get(_IMMOBILE, category="status", return_list=True):
            self.msg(
                f"You can't move while you're {iter_to_str(sorted(statuses), endsep='or')}."
            )
            return False

        # check if we're in combat
        if self.in_combat:
            self.msg("You can't leave while in combat.")
            return False
        """
        #A command that can't be used while the character is busy.
        if self.ndb.busy:
            return False
            
        else:
            return super().at_pre_move(destination, **kwargs)

    def at_pre_object_receive(self, moved_object, source_location, **kwargs):
        """
        Hook called by Evennia before moving an object here. Return False to abort move.

        Args:
            moved_object (Object): Object to move into this one (that is, into inventory).
            source_location (Object): Source location moved from.
            **kwargs: Passed from move operation; the `move_type` is useful; if someone is giving
                us something (`move_type=='give'`) we want to ask first.

        Returns:
            bool: If move should be allowed or not.

        """
        # this will raise EquipmentError if inventory is full
        return self.equipment.validate_slot_usage(moved_object)
    
    def at_object_receive(self, moved_object, source_location, **kwargs):
        """
        Hook called by Evennia as an object is moved here. We make sure it's added
        to the equipment handler.

        Args:
            moved_object (Object): Object to move into this one (that is, into inventory).
            source_location (Object): Source location moved from.
            **kwargs: Passed from move operation; unused here.

        """
        try:
            self.equipment.add(moved_object)
        except EquipmentError as err:
            log_trace(f"at_object_receive error: {err}")

    def at_pre_object_leave(self, leaving_object, destination, **kwargs):
        """
        Hook called when dropping an item. We don't allow to drop wielded/worn items
        (need to unwield/remove them first). Return False to

        """
        return True
    
    def at_object_leave(self, moved_object, destination, **kwargs):
        """
        Called just before an object leaves from inside this object

        Args:
            moved_obj (Object): The object leaving
            destination (Object): Where `moved_obj` is going.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        self.equipment.remove(moved_object)

    def at_defeat(self):
        """
        This happens when character drops <= 0 HP.

        """
        if self.location.allow_death:
            # this allow rooms to have non-lethal battles
            self.at_death()
        else:
            self.location.msg_contents(
                "$You() $conj(collapse) in a heap, alive but beaten.",
                from_obj=self)
            self.heal(self.hp_max)
    
    def at_death(self):
        """
        Called when character dies.

        """
        pass

    def at_pre_loot(self):
        """
        Called before allowing to loot. Return False to block enemy looting.
        """
        # don't allow looting in pvp
        return not self.location.allow_pvp

    def at_looted(self, looter):
        """
        Called when being looted.

        """
        pass

    def add_xp(self, xp):
        """
        Add new XP.

        Args:
            xp (int): The amount of gained XP.

        Returns:
            bool: If a new level was reached or not.

        Notes:
            level 1 -> 2 = 1000 XP
            level 2 -> 3 = 2000 XP etc

        """
        self.xp += xp
        next_level_xp = self.level * self.xp_per_level
        self.msg(f"You gain {xp} XP.")
        return self.xp >= next_level_xp

    def level_up(self, *abilities):
        """
        Perform the level-up action.

        Args:
            *abilities (str): A set of abilities (like 'strength', 'dexterity' (normally 3)
                to upgrade by 1. Max is usually +10.
        Notes:
            We block increases above a certain value, but we don't raise an error here, that
            will need to be done earlier, when the user selects the ability to increase.

        """

        self.level += 1
        for ability in set(abilities[:3]):
            # limit to max amount allowed, each one unique
            try:
                # set at most to the max bonus
                current_bonus = getattr(self, ability)
                setattr(
                    self,
                    ability,
                    min(10, current_bonus + 1),
                )
            except AttributeError:
                pass

        # update hp
        self.hp_max = max(self.hp_max + 1, dice.roll(f"{self.level}d8"))
        self.msg(f"|yCongratulations! You have leveled up to Level {self.level}!|n")

    def update_prompt(self):
        """
        Updates the prompt displayed to the player.
        """
        if not self.prompt_on:
            return
        prompt_text = display_meter(self.hp,self.hp_max)
        self.msg(prompt=prompt_text)

    def update_stats(self):
        """
        Update the stats of the character.
        """
        if hasattr(self, "is_pc") and self.is_pc:
            self.update_prompt()

    def get_available_dungeon_templates(self, completed_dungeons):
        """
        Get a list of dungeon templates available to the character.

        Args:
            completed_dungeons (list): A list of completed dungeon template identifiers.

        Returns:
            list: A list of available dungeon templates.
        """
        dungeon_manager = self.search("dungeon_manager", global_search=True)

        if not dungeon_manager:
            return []

        templates = dungeon_manager.get_templates()
        available_templates = [template for template in templates if template.get("id") not in completed_dungeons]
        return available_templates
    
class Party:
    """
    Represents a party of characters.
    """

    def __init__(self, leader, name):
        self.leader_id = leader.id  # Store the leader's object ID
        self.name = name  # The name of the party
        self.member_ids = {leader.id}  # Store members by their object IDs

    def add_member(self, member):
        """
        Add a new member to the party.

        Args:
            member (Object): The character to add.
        """
        if member.id not in self.member_ids:
            self.member_ids.add(member.id)
            return True
        return False

    def remove_member(self, member):
        """
        Remove a member from the party.

        Args:
            member (Object): The character to remove.
        """
        if member.id in self.member_ids:
            self.member_ids.remove(member.id)
            return True
        return False

    def get_members(self):
        """
        Get the actual objects of all members.

        Returns:
            list: A list of Character objects in the party.
        """
        return [char for char in self._resolve_ids(self.member_ids)]

    def _resolve_ids(self, id_set):
        """
        Resolve a set of object IDs to actual objects.

        Args:
            id_set (set): A set of object IDs.

        Returns:
            list: The resolved objects.
        """
        return [obj for obj in ObjectDB.objects.filter(id__in=id_set)]

    def disband(self):
        """
        Disband the party.
        """
        members = self.get_members()
        for member in members:
            member.db.party = None  # Clear the party reference for all members
        self.member_ids.clear()
