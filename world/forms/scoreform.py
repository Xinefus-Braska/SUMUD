FORMCHAR = "x"
TABLECHAR = "c"

FORM = '''
.---------------------.                       .---------------------.
| Player: xxxxx1xxxxx |                       | Account: xxxxx2xxxx |
| Race  : xxxxx3xxxxx |                       | Trust  : xxxxx4xxxx |
 >-----------------------------------------------------------------<
|           TRAITS           |               STATS                  |
| ~~~~~~~~~~~~~~~~~~~~~~~~~~ | ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ |
| Level:               xx5xx | cccccccccccccccccccccccccccccccccccc |
| LF:      xxxxxxxx6xxxxxxxx | cccccccccccccccccccccccccccccccccccc |
| LFbase:  xxxxxxxx7xxxxxxxx | ccccccccccccccccccAccccccccccccccccc |
| Limit:           xxxx/xxxx | cccccccccccccccccccccccccccccccccccc |
|                            | cccccccccccccccccccccccccccccccccccc |
---------------------------------------------------------------------
'''

'''
.------------------------------------------------------.
|                                                      |
|    Player: xxxxx1xxxxx      Account: xxxxx2xxxxx     |
|      Race: xxxxx3xxxxx        Trust: xxxxx4xxxxx     |
|                                                      |
 >----------------------------------------------------<
|           TRAITS            |         STATS          |
| ~~~~~~~~~~~~~~~~~~~~~~~~~~~ | ~~~~~~~~~~~~~~~~~~~~~  |
| Level: xx5xx                |     |Base | Mod |Total |
| HP: x6x/x7x                 | ~~~~+~~~~~+~~~~~+~~~~~ |
| LF: xxxxxxxx8xxxxxxxx       | INT | x9x | x10 | x11x |
| LFbase: xxxxxxxx12xxxxxxx   | DEX | x13 | x14 | x15x |
|                             | CON | x16 | x17 | x18x |
|                             | ~~~~~~~~~~~~~~~~~~~~~~ |
|                             |   LIMIT: x19x/x20x     |
--------------------------------------------------------
'''