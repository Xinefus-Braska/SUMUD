"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

from evennia.objects.objects import DefaultCharacter

from .objects import ObjectParent
from evennia.utils import lazy_property
from evennia.contrib.rpg.traits import TraitHandler


class Character(ObjectParent, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Object child classes like this.

    """

    @lazy_property
    def traits(self):
        # this adds the handler as .traits
        return TraitHandler(self, db_attribute_key="traits")
    
    @lazy_property
    def stats(self):
        # this adds the handler as .stats
        return TraitHandler(self, db_attribute_key="stats")

    @lazy_property
    def skills(self):
        # this adds the handler as .skills
        return TraitHandler(self, db_attribute_key="skills")

    def at_object_creation(self):

        self.traits.clear()
        self.skills.clear()
        self.stats.clear()

        self.traits.add( "lf_base", "LifeforceBase", trait_type="static", base=1000, mod=0 )
        self.traits.add( "lf", "Lifeforce", trait_type="gauge", base=0, max=1000000000000, mod=0 )
        self.stats.add( "str", "Strength", trait_type="static", base=10, max=100, mod=0 )
        self.stats.add( "str_base", "StrengthBase", trait_type="static", base=10, max=100, mod=0 )
        self.stats.add( "dex", "Dexterity", trait_type="static", base=10, max=100, mod=0 )
        self.stats.add( "dex_base", "DexterityBase", trait_type="static", base=10, max=100, mod=0 )
        self.stats.add( "int", "Intelligence", trait_type="static", base=10, max=100, mod=0 )
        self.stats.add( "int_base", "IntelligenceBase", trait_type="static", base=10, max=100, mod=0 )
        self.traits.add( "level", "Level", trait_type="static", base=1, max=100, mod=0 )
        self.stats.add( "limit", "Limit", trait_type="static", base=0, max=1000, mod=0 )

        # set up intial equipment slots for the character. Since the character
        # is new and has no mutations, there won't be slots like tail or extra
        # arms
        self.db.limbs = ( ('head', ('head', 'face', 'ears', 'neck')),
                          ('torso', ('chest', 'back', 'waist')),
                          ('arms', ('shoulders', 'arms', 'hands', 'ring')),
                          ('legs', ('legs', 'feet')),
                          ('weapon', ('main hand', 'off hand')) )
        
        # define slots that go with the limbs.
        # TODO: Write a function for changing slots if/when mutations cause
        # new limbs to be grown or damage causes them to be lost
        self.db.slots = {
            'head': None,
            'face': None,
            'ears': None,
            'neck': None,
            'chest': None,
            'back': None,
            'waist': None,
            'shoulders': None,
            'arms': None,
            'hands': None,
            'ring': None,
            'legs': None,
            'feet': None,
            'main hand': None,
            'off hand': None
        }

    pass


class NonPlayerCharacter(DefaultCharacter):
    """
    The generic NPC, such as shopkeepers, trainers, etc.
    Inherits the DefaultCharacter class, without any of the Character attributes.
    """

class MobCharacter(Character):
    """
    Everything you can grind and kill to level up!
    Inherits the Character class so that we can use all of their attributes. 
    """