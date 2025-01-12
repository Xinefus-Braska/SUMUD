from evennia.objects.objects import DefaultExit

class SUExit(DefaultExit):
    def at_traverse(self, traversing_object, target_location, **kwargs):
        if traversing_object.ndb.busy:
            traversing_object.msg("|rYou are too busy for that.|n")
        elif traversing_object.ndb.combat:
            traversing_object.msg("|rYou can't leave while in combat.|n")
        else:
            super().at_traverse(traversing_object, target_location, **kwargs)

