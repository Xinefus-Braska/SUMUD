"""
Character class.

"""

from evennia.objects.objects import DefaultCharacter
from evennia.typeclasses.attributes import AttributeProperty
from evennia.utils.logger import log_trace
from evennia.utils.utils import lazy_property

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
        #print(f"'{self.key}' called at_attacked")
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
        pass

    def at_pay(self, amount):
        """When paying coins, make sure to never detract more than we have"""
        amount = min(amount, self.coins)
        self.coins -= amount
        return amount
        
    def at_looted(self, looter):
        """Called when looted by another entity""" 
        # default to stealing some coins 
        max_steal = dice.roll("1d10") 
        stolen = self.at_pay(max_steal)
        looter.coins += stolen

    def pre_loot(self, defeated_enemy):
        """
        Called just before looting an enemy.

        Args:
            defeated_enemy (Object): The enemy soon to loot.

        Returns:
            bool: If False, no looting is allowed.

        """
        pass

    def at_do_loot(self, defeated_enemy):
        """
        Called when looting another entity.

        Args:
            defeated_enemy: The thing to loot.

        """
        defeated_enemy.at_looted(self)

    def post_loot(self, defeated_enemy):
        """
        Called just after having looted an enemy.

        Args:
            defeated_enemy (Object): The enemy just looted.

        """
        pass

class SUCharacter(LivingMixin, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Object child classes like this.

    """
    is_pc = True

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
        This happens when character drops <= 0 HP. For Characters, this means rolling on
        the death table.

        """
        if self.location.allow_death:
            # this allow rooms to have non-lethal battles
            dice.roll_death(self)
        else:
            self.location.msg_contents(
                "$You() $conj(collapse) in a heap, alive but beaten.",
                from_obj=self)
            self.heal(self.hp_max)
    
    def at_death(self):
        """
        Called when character dies.

        """
        self.location.msg_contents(
            "|r$You() $conj(collapse) in a heap.\nDeath embraces you ...|n",
            from_obj=self,
        )

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

    def update_prompt(self):
        """
        Updates the prompt displayed to the player.
        """
        #hp = self.db.hp if hasattr(self, "db") and self.db.hp else "?"
        #hp_max = self.db.hp_max if hasattr(self, "db") and self.db.hp_max else "?"
        prompt_text = display_meter(self.hp,self.hp_max)
        self.msg(prompt=prompt_text)

    def update_stats(self):
        """
        Update the stats of the character.
        """
        self.update_prompt()
