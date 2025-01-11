from evennia import DefaultScript
from evennia.objects.models import ObjectDB 

class PartyManager(DefaultScript):
    """
    A persistent script to manage all active parties.
    """

    def at_script_creation(self):
        self.key = "party_manager"
        self.desc = "Manages all active parties."
        self.persistent = True
        self.db.parties = {}  # Dictionary to store parties by name or ID
        self.db.MAX_PARTY_SIZE = 5  # Maximum number of members allowed in a party

    @property
    def MAX_PARTY_SIZE(self):
        """
        Convenience property to access the maximum party size.
        """
        return self.db.MAX_PARTY_SIZE
    
    def create_party(self, leader, name):
        """
        Create a new party.

        Args:
            leader (Object): The leader of the party.
            name (str): The name of the party.

        Returns:
            dict: The created party data.
        """
        if name in self.db.parties:
            return None  # Party name already exists

        party = {
            "name": name,
            "leader_id": leader.id,
            "member_ids": {leader.id},
        }
        self.db.parties[name] = party
        return party

    def get_party(self, name):
        """
        Retrieve a party by name.

        Args:
            name (str): The name of the party.

        Returns:
            dict: The party data, or None if not found.
        """
        return self.db.parties.get(name)
    
    def add_member_to_party(self, member, party_name):
        party = self.get_party(party_name)
        if not party:
            return False
        
        # Check if the party is already full
        if len(party["member_ids"]) >= self.MAX_PARTY_SIZE:
            member.msg(f"|rThe party '{party_name}' is already full. Maximum size is {self.MAX_PARTY_SIZE}.|n")
            return False
        
        party["member_ids"].add(member.id)
        return True

    def get_party_members(self, party_name):
        party = self.get_party(party_name)
        if not party:
            return []
        return [
            obj for obj in ObjectDB.objects.filter(id__in=party["member_ids"])
        ]

    def remove_member_from_party(self, member, party_name):
        """Remove a member from a party."""
        party = self.get_party(party_name)
        if not party:
            return False
        if member.id in party["member_ids"]:
            party["member_ids"].remove(member.id)
            self.db.parties[party_name] = party  # Save the updated party back to the script
            return True
        return False

    def remove_party(self, name):
        """
        Disband a party.

        Args:
            name (str): The name of the party to remove.
        """
        if name in self.db.parties:
            del self.db.parties[name]
