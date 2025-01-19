r"""
Evennia settings file.

The available options are found in the default settings file found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

######################################################################
# Evennia base server config
######################################################################

# This is the name of your game. Make it catchy!
SERVERNAME = "SUMUD"

######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")

# Disable Django's debug mode
DEBUG = False
# Disable the in-game equivalent
IN_GAME_ERRORS = False

# A list of ports the Evennia telnet server listens on Can be one or many.
TELNET_PORTS = [8002]
# Optional for security. Restrict which telnet
# interfaces we should accept. Should be set to your
# outward-facing IP address(es). Default is ´0.0.0.0´
# which accepts all interfaces.
TELNET_INTERFACES = ['0.0.0.0']
# Activate Telnet+SSL protocol (SecureSocketLibrary) for supporting clients
SSL_ENABLED = True
# Ports to use for Telnet+SSL
SSL_PORTS = [8005]
SSL_INTERFACES = ['0.0.0.0']
# OOB (out-of-band) telnet communication allows Evennia to communicate
# special commands and data with enabled Telnet clients. This is used
# to create custom client interfaces over a telnet connection. To make
# full use of OOB, you need to prepare functions to handle the data
# server-side (see INPUT_FUNC_MODULES). TELNET_ENABLED is required for this
# to work.
TELNET_OOB_ENABLED = False
# Activate SSH protocol communication (SecureShell)
SSH_ENABLED = False
# Ports to use for SSH
SSH_PORTS = [8006]
# The webserver sits behind a Portal proxy. This is a list
# of tuples (proxyport,serverport) used. The proxyports are what
# the Portal proxy presents to the world. The serverports are
# the internal ports the proxy uses to forward data to the Server-side
# webserver (these should not be publicly open)
WEBSERVER_PORTS = [(8003, 8007)]
# Server-side websocket port to open for the webclient. Note that this value will
# be dynamically encoded in the webclient html page to allow the webclient to call
# home. If the external encoded value needs to be different than this, due to
# working through a proxy or docker port-remapping, the environment variable
# WEBCLIENT_CLIENT_PROXY_PORT can be used to override this port only for the
# front-facing client's sake.
WEBSOCKET_CLIENT_PORT = 8004
# Set the FULL URI for the websocket, including the scheme
WEBSOCKET_CLIENT_URL = "wss://mud.jbhlmh.ca/ws"
# The Server opens an AMP port so that the portal can
# communicate with it. This is an internal functionality of Evennia, usually
# operating between two processes on the same machine. You usually don't need to
# change this unless you cannot use the default AMP port/host for
# whatever reason.
AMP_PORT = 8008
# This is a security setting protecting against host poisoning
# attacks.  It defaults to allowing all. In production, make
# sure to change this to your actual host addresses/IPs.
ALLOWED_HOSTS = ['192.168.88.50', 'mud.jbhlmh.ca', '192.168.88.20', '192.168.88.10']
# The url address to your server, like mymudgame.com. This should be the publicly
# visible location. This is used e.g. on the web site to show how you connect to the
# game over telnet. Default is localhost (only on your machine).
SERVER_HOSTNAME = "mud.jbhlmh.ca"
# This needs to be set to your website address for django or you'll receive a
# CSRF error when trying to log on to the web portal
CSRF_TRUSTED_ORIGINS = ['https://mud.jbhlmh.ca']

# Discord integration support
DISCORD_ENABLED = True
# Local time zone for this installation. All choices can be found here:
# http://www.postgresql.org/docs/8.0/interactive/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = "EST"

# Connection Stuffs

# Enable/Disable new accounts
NEW_ACCOUNT_REGISTRATION_ENABLED = False
# Different Multisession modes allow a player (=account) to connect to the
# game simultaneously with multiple clients (=sessions).
#  0 - single session per account (if reconnecting, disconnect old session)
#  1 - multiple sessions per account, all sessions share output
#  2 - multiple sessions per account, one session allowed per puppet
#  3 - multiple sessions per account, multiple sessions per puppet (share output)
#      session getting the same data.
MULTISESSION_MODE = 3
# The maximum number of characters allowed by be created by the default ooc
# char-creation command. This can be seen as how big of a 'stable' of characters
# an account can have (not how many you can puppet at the same time). Set to
# None for no limit.
MAX_NR_CHARACTERS = 10
# How many *different* characters an account can puppet *at the same time*. A value
# above 1 only makes a difference together with MULTISESSION_MODE > 1.
MAX_NR_SIMULTANEOUS_PUPPETS = 3
# Whether we should create a character with the same name as the account when
# a new account is created. Together with AUTO_PUPPET_ON_LOGIN, this mimics
# a legacy MUD, where there is no difference between account and character.
AUTO_CREATE_CHARACTER_WITH_ACCOUNT = False
# BASE_ACCOUNT_TYPECLASS = 
#CHARGEN_MENU = "world.character.chargen"
BASE_ACCOUNT_TYPECLASS = "world.character.account.SUAccount"
BASE_CHARACTER_TYPECLASS = "world.character.characters.SUCharacter"
BASE_ROOM_TYPECLASS = "world.rooms.rooms.SURoom"
BASE_EXIT_TYPECLASS = "world.rooms.suexits.SUExit"
# BASE_OBJECT_TYPECLASS = 
#PROTOTYPE_MODULES = "world.character.mobprototypes"
COMMAND_DEFAULT_CLASS = "commands.command.MuxCommand"
# Whether an account should auto-puppet the last puppeted puppet when logging in. This
# will only work if the session/puppet combination can be determined (usually
# MULTISESSION_MODE 0 or 1), otherwise, the player will end up OOC. Use
# MULTISESSION_MODE=0, AUTO_CREATE_CHARACTER_WITH_ACCOUNT=True and this value to
# mimic a legacy mud with minimal difference between Account and Character. Disable
# this and AUTO_PUPPET to get a chargen/character select screen on login.
AUTO_PUPPET_ON_LOGIN = False

# XYZGrid stuffs
# EXTRA_LAUNCHER_COMMANDS['xyzgrid'] = 'evennia.contrib.grid.xyzgrid.launchcmd.xyzcommand'
# PROTOTYPE_MODULES += ['evennia.contrib.grid.xyzgrid.prototypes']
#Basic Map Stuffs
BASIC_MAP_SIZE = 5  # This changes the default map width/height.

# uncomment if you want to lock the server down for maintenance.
# LOCKDOWN_MODE = True


# Evennia Game Index
#GAME_INDEX_ENABLED = True 

GAME_INDEX_LISTING = {
    # required 
    'game_status': 'pre-alpha',            # pre-alpha, alpha, beta, launched
    'listing_contact': "hahnhell@gmail.com",  # not publicly shown.
    'short_description': 'Grind your Power to the top!',    

    # optional 
    'long_description':
        "Play and live like one of your favourite manga/anime characters! Power-up \n"
        "and become the strongest in the Universe in whatever way you like! Be your \n"
        "favourite hero or pick and chose something unique!",
    'telnet_hostname': 'mud.jbhlmh.ca',            
    'telnet_port': '8002',                     
    'web_client_url': 'mud.jbhlmh.ca/',   
    'game_website': 'mud.jbhlmh.ca/',
    # 'game_name': 'MyGame',  # set only if different than settings.SERVERNAME
}