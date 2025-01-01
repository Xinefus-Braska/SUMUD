from evennia import DefaultObject, AttributeProperty, search_object, create_object
from evennia.utils.utils import make_iter
from world.utils.utils import get_obj_stats
from world.utils.enums import WieldLocation, ObjType, Ability
from world.utils import rules

_BARE_HANDS = None 

class SUObject(DefaultObject): 
    """ 
    Base for all SU objects. 
    
    """ 
    inventory_use_slot = WieldLocation.BACKPACK
    size = AttributeProperty(1, autocreate=False)
    value = AttributeProperty(0, autocreate=False)
    
    # this can be either a single type or a list of types (for objects able to be 
    # act as multiple). This is used to tag this object during creation.
    obj_type = ObjType.GEAR

    # default evennia hooks

    def at_object_creation(self): 
        """Called when this object is first created. We convert the .obj_type 
        property to a database tag."""
        
        for obj_type in make_iter(self.obj_type):
            self.tags.add(self.obj_type.value, category="obj_type")

    def get_display_header(self, looker, **kwargs):
        """The top of the description""" 
        return "" 

    def get_display_desc(self, looker, **kwargs):
        """The main display - show object stats""" 
        return get_obj_stats(self, owner=looker)

    # custom SU methods

    def has_obj_type(self, objtype): 
        """Check if object is of a certain type""" 
        return objtype.value in make_iter(self.obj_type)

    def at_pre_use(self, *args, **kwargs): 
        """Called before use. If returning False, can't be used""" 
        return True 

    def use(self, *args, **kwargs): 
        """Use this object, whatever that means""" 
        pass 

    def post_use(self, *args, **kwargs): 
        """Always called after use.""" 
        pass

    def get_help(self):
        """Get any help text for this item"""
        return "No help for this item"

class SUQuestObject(SUObject):
    """Quest objects should usually not be possible to sell or trade."""
    obj_type = ObjType.QUEST
 
class SUTreasure(SUObject):
    """Treasure is usually just for selling for coin"""
    obj_type = ObjType.TREASURE
    value = AttributeProperty(100, autocreate=False)

class SUConsumable(SUObject): 
    """An item that can be used up""" 
    
    obj_type = ObjType.CONSUMABLE
    value = AttributeProperty(0.25, autocreate=False)
    uses = AttributeProperty(1, autocreate=False)
    
    def at_pre_use(self, user, target=None, *args, **kwargs):
        """Called before using. If returning False, abort use."""
        if target and user.location != target.location:
            user.msg("You are not close enough to the target!")
            return False
		
        if self.uses <= 0:
            user.msg(f"|w{self.key} is used up.|n")
            return False

    def use(self, user, *args, **kwargs):
        """Called when using the item""" 
        pass
    
    def at_post_use(self, user, *args, **kwargs):
        """Called after using the item""" 
        # detract a usage, deleting the item if used up.
        self.uses -= 1
        if self.uses <= 0: 
            user.msg(f"{self.key} was used up.")
            self.delete()

class SUWeapon(SUObject): 
    """Base class for all weapons"""

    obj_type = ObjType.WEAPON 
    inventory_use_slot = AttributeProperty(WieldLocation.WEAPON_HAND, autocreate=False)
    quality = AttributeProperty(3, autocreate=False)
    
    attack_type = AttributeProperty(Ability.STR, autocreate=False)
    defend_type = AttributeProperty(Ability.ARMOR, autocreate=False)
    
    damage_roll = AttributeProperty("1d6", autocreate=False)


    def at_pre_use(self, user, target=None, *args, **kwargs):
        if target and user.location != target.location:
           # we assume weapons can only be used in the same location
           user.msg("You are not close enough to the target!")
           return False
        # Not using object durability for now
        #if self.quality is not None and self.quality <= 0:
        #   user.msg(f"{self.get_display_name(user)} is broken and can't be used!")
        #   return False
        return super().at_pre_use(user, target=target, *args, **kwargs)

    def use(self, attacker, target, *args, advantage=False, disadvantage=False, **kwargs):
        """When a weapon is used, it attacks an opponent"""
        location = attacker.location

        is_hit, quality, txt = rules.dice.opposed_saving_throw(
            attacker,
            target,
            attack_type=self.attack_type,
            defense_type=self.defense_type,
            advantage=advantage,
            disadvantage=disadvantage,
        )
        location.msg_contents(
            f"$You() $conj(attack) $You({target.key}) with {self.key}.", #: {txt}
            from_obj=attacker, mapping={target.key: target},
        )
        if is_hit:
            # enemy hit, calculate damage
            dmg = rules.dice.roll(self.damage_roll)

            if quality is Ability.CRITICAL_SUCCESS:
                # double damage roll for critical success
                dmg += rules.dice.roll(self.damage_roll)
                message = (
                    f" $You() |ycritically|n |g$conj(hit)|n $You({target.key}) for |r{dmg}|n damage!"
                )
            else:
                message = f" $You() |g$conj(hit)|n $You({target.key}) for |r{dmg}|n damage!"

            location.msg_contents(message, from_obj=attacker, mapping={target.key: target})
            # call hook
            target.at_damage(dmg, attacker=attacker)

        else:
        # a miss
            message = f" $You() |r$conj(miss)|n $You({target.key})."
            # Not using object durability for now
            #if quality is Ability.CRITICAL_FAILURE:
            #    message += ".. it's a |rcritical miss!|n, damaging the weapon."
            #if self.quality is not None:
            #    self.quality -= 1
            location.msg_contents(message, from_obj=attacker, mapping={target.key: target})

    def at_post_use(self, user, *args, **kwargs):
        pass
        # Not using object durability for now
        #if self.quality is not None and self.quality <= 0:
        #    user.msg(f"|r{self.get_display_name(user)} breaks and can no longer be used!")

class SURuneStone(SUWeapon, SUConsumable): 
    """Base for all magical rune stones"""
    
    obj_type = (ObjType.WEAPON, ObjType.MAGIC)
    inventory_use_slot = WieldLocation.TWO_HANDS  # always two hands for magic
    quality = AttributeProperty(3, autocreate=False)

    attack_type = AttributeProperty(Ability.INT, autocreate=False)
    defend_type = AttributeProperty(Ability.DEX, autocreate=False)
    
    damage_roll = AttributeProperty("1d8", autocreate=False)

    def at_post_use(self, user, *args, **kwargs):
        """Called after usage/spell was cast""" 
        self.uses -= 1 
        # we don't delete the rune stone here, but 
        # it must be reset on next rest.
        
    def refresh(self):
        """Refresh the rune stone (normally after rest)"""
        self.uses = 1

class SUArmor(SUObject): 
    obj_type = ObjType.ARMOR
    inventory_use_slot = WieldLocation.BODY 

    armor = AttributeProperty(1, autocreate=False)
    quality = AttributeProperty(3, autocreate=False)

class SUShield(SUArmor):
    obj_type = ObjType.SHIELD
    inventory_use_slot = WieldLocation.SHIELD_HAND 

class SUHelmet(SUArmor): 
    obj_type = ObjType.HELMET
    inventory_use_slot = WieldLocation.HEAD

class WeaponBareHands(SUWeapon):
    obj_type = ObjType.WEAPON
    inventory_use_slot = WieldLocation.WEAPON_HAND
    attack_type = Ability.STR
    defense_type = Ability.ARMOR
    damage_roll = "1d4"
    quality = None  # let's assume fists are indestructible ...

def get_bare_hands(): 
    """Get the bare hands""" 
    global _BARE_HANDS
    if not _BARE_HANDS: 
        _BARE_HANDS = search_object("bare hands", typeclass=WeaponBareHands).first()
    if not _BARE_HANDS:
        _BARE_HANDS = create_object(WeaponBareHands, key="bare hands")
    return _BARE_HANDS