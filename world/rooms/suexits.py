from evennia.objects.objects import DefaultExit


class SUExit(DefaultExit):
    def at_traverse(self, traversing_object, target_location, **kwargs):
        if traversing_object.ndb.busy:
            traversing_object.msg("|yYou are too busy for that.|n")
        else:
            super().at_traverse(traversing_object, target_location, **kwargs)

