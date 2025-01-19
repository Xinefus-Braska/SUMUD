from evennia import DefaultAccount, create_object

class SUAccount(DefaultAccount):
    """
    Custom account class to create and link shared rooms for the account.
    """

    def at_account_creation(self):
        """
        Called when a new account is created. Sets up shared rooms and connects them with exits.
        """
        # Create the House or Home
        house = create_object("world.rooms.rooms.SUHouse", key=f"{self.key}'s House")
        house.db.desc = "This is your cozy home. It feels warm and welcoming."
        house.tags.add("shared_room")
        self.db.house = house

        # Create the Armoury
        armoury = create_object("world.rooms.rooms.SUArmoury", key=f"{self.key}'s Armoury")
        armoury.db.desc = "This is a secure room where you can store items and currency."
        armoury.tags.add("shared_room")
        self.db.armoury = armoury

        # Create the Rift
        rift = create_object("world.rooms.rooms.SURift", key=f"{self.key}'s Rift")
        rift.db.desc = "A mysterious room with portals leading to different parts of the world."
        rift.tags.add("shared_room")
        self.db.rift = rift

        # Connect the rooms with two-way exits
        self._create_exits(house, armoury, "Armoury", "House")
        self._create_exits(armoury, rift, "Rift", "Armoury")
        self._create_exits(rift, house, "House", "Rift")

        # Notify the account
        self.msg("Shared rooms have been created and connected for your account.")

    def _create_exits(self, room_from, room_to, exit_to_name, exit_from_name):
        """
        Helper method to create two-way exits between rooms.
        """
        # Create exit from `room_from` to `room_to`
        exit_to = create_object(
            typeclass="world.rooms.suexits.SUExit",
            key=exit_to_name,
            location=room_from,
            destination=room_to,
        )

        # Create return exit from `room_to` to `room_from`
        exit_from = create_object(
            typeclass="world.rooms.suexits.SUExit",
            key=exit_from_name,
            location=room_to,
            destination=room_from,
        )
