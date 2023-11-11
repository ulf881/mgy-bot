"""
    Modulo para games. AKA CrappyDungeon
"""
import logging
import asyncio
from random import randint
from collections import Counter
from discord.ext import commands

log = logging.getLogger("Games")
TEMPO = 7


def most_common(lst: list):
    """Retorna item mais comum da lista"""
    data = Counter(lst)
    log.info(data.most_common(1)[0][0])
    return data.most_common(1)[0][0]


async def title(ctx: commands.Context):
    """Title screen do crappy"""
    # await ctx.send("  #### ####   ###  ####  ####  #     # ")
    # await ctx.send(" #     #   # #   # #   # #   #  #   #  ")
    # await ctx.send(" #     ####  ##### #   # #   #   # #   ")
    # await ctx.send(" #     # #   #   # ####  ####     #    ")
    # await ctx.send("  #### #  #  #   # #     #        #    ")

    # await ctx.send("    ####  #   # #   #  ####  ####  ####  #   # ")
    # await ctx.send("    #   # #   # ##  # #      #    #    # ##  # ")
    # await ctx.send("    #   # #   # # # # #  ### ###  #    # # # # ")
    # await ctx.send("    #   # #   # #  ## #    # #    #    # #  ## ")
    # await ctx.send("    ####   ###  #   #  ####  ####  ####  #   # ")

    # await ctx.send("         #### ####   ###  #    #    # #     #### ####  ")
    # await ctx.send("        #     #   # #   # #    #    # #     #    #   # ")
    # await ctx.send("        #     ####  #####  #  # #  #  #     ###  ####  ")
    # await ctx.send("        #     # #   #   #   # # # #   #     #    # #   ")
    # await ctx.send("         #### #  #  #   #    #   #    ##### #### #  #  ")
    await ctx.send(
        "Todas as mensagens a partir desse ponto serão deletas ao fim do jogo"
    )
    await ctx.send(
        " \n -> Welcome to Crappy Dungeon Crawler v1.2 for *P*Y*T*H*O*N*!* <- \n"
        + " Follow the instructions on the screen and type your commands to play\n"
        + " Kill monsters, disarm traps and collect coins and gems to increase your SCORE\n"
        + " Get a *100* SCORE to *W*I*N*!!"
    )


class Games(commands.Cog, name="Games"):
    """
    Games
    """

    def __init__(self, bot):
        self.bot = bot
        self.lista_acoes = []
        self.score = 0

    @commands.command(aliases=["st", "init", "cdc", "crappy", "dungeon", "crawler"])
    async def start(self, ctx: commands.Context):
        """Inicia partida de crappy dungeon"""
        if not self.bot.game:
            await title(ctx)
            self.bot.game = True
            await self.crappy_dungeon(ctx)
            await ctx.channel.purge(limit=self.bot.total_mensagem + 3)
            self.bot.total_mensagem = 0
            self.bot.acoes = []
            self.bot.game = False
            await ctx.send("YOUR SCORE WAS " + str(self.score))
            # self.bot.game = CrappyDungeon(ctx, jogada)

    async def crappy_dungeon(self, ctx: commands.Context):
        """Main do jogo Crappy Dungeon By Max"""

        # generates player states
        playerATK = 1 + randint(1, 3)
        playerDEF = 3 + randint(1, 3)

        # sets counters and score

        playerState = 1  # 1 == ALIVE, 0 == DEAD
        self.score = 0
        counter = 0  # move counter
        zapCount = 20 + randint(1, 10)  # count to activate stat reset zap room

        # monster name letters
        nmSt = ["N", "M", "B", "G", "K"]
        vog = ["a", "e", "i", "o", "u"]
        con = ["h", "k", "l", "j", "k"]

        # adjectives
        roomADJ = [
            "dank",
            "smelly",
            "moist",
            "dusty",
            "cluterred",
            "dark",
            "unnaturally dry",
            "mossy",
        ]
        monsterADJ = [
            "green",
            "yellow",
            "red",
            "stinky",
            "ugly",
            "charismatic",
            "cross eyed",
            "handsome",
            "toothless",
            "tall",
            "short",
            "fat",
            "skinny",
        ]
        trapADJ = [
            "pit",
            "spike",
            "swinging axe",
            "falling rock",
            "weird",
            "magical",
            "bear",
            "small",
            "big",
        ]

        while playerState != 0 and self.score < 100 and self.bot.game:
            # generates rand num for room creation
            roomGen = randint(1, 5)
            roomAdjective = roomADJ[randint(0, len(roomADJ) - 1)]
            monsterAdjective = monsterADJ[randint(0, len(monsterADJ) - 1)]
            trapAdjective = trapADJ[randint(0, len(trapADJ) - 1)]

            # debug line, uncomment to test specific room types
            # roomGen = 4

            # change difficult (monster and trap stats) according to # of moves
            if counter < 20:
                monsterNAME = (
                    nmSt[randint(0, 4)]
                    + vog[randint(0, 4)]
                    + con[randint(0, 4)]
                    + vog[randint(0, 4)]
                    + con[randint(0, 4)]
                )  # random monster name
                monsterATK = 1 + randint(1, 3)
                monsterDEF = 3 + randint(1, 3)
                monsterSCORE = 1 + int(monsterDEF / 2)
                trapATK = 1 + randint(1, 6)
            elif counter == 20:
                await ctx.send("\n ATTENTION! \n Things will get harder!\n")
                monsterNAME = (
                    nmSt[randint(0, 4)]
                    + vog[randint(0, 4)]
                    + con[randint(0, 4)]
                    + vog[randint(0, 4)]
                    + con[randint(0, 4)]
                )
                monsterATK = 1 + randint(1, 3)
                monsterDEF = 3 + randint(1, 3)
                monsterSCORE = 1 + int(monsterDEF / 2)
                trapATK = 3 + randint(1, 6)
            else:
                monsterNAME = (
                    nmSt[randint(0, 4)]
                    + vog[randint(0, 4)]
                    + con[randint(0, 4)]
                    + vog[randint(0, 4)]
                    + con[randint(0, 4)]
                )
                monsterATK = 1 + randint(1, 3)
                monsterDEF = 3 + randint(1, 3)
                monsterSCORE = 1 + int(monsterDEF / 2)
                trapATK = 3 + randint(1, 6)

            # display start up text
            if counter == 0:
                await ctx.send(
                    "\n Your ATK is "
                    + str(playerATK)
                    + " | Your DEF is "
                    + str(playerDEF)
                    + "\n Your score is "
                    + str(self.score)
                    + "\n You made "
                    + str(counter)
                    + " moves"
                    + "\n-->Type 1 to START or 0 to GIVE UP:  \n"
                )
                await asyncio.sleep(TEMPO)
                if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                    self.bot.game = False
                    log.info("Encerrando jogo")
                    return
                playerState = int(most_common(self.bot.acoes))
                self.bot.acoes = []

            # or continue text
            else:
                await ctx.send(
                    "\n Your score is "
                    + str(self.score)
                    + "\n You made "
                    + str(counter)
                    + " moves "
                    + "\n-->Type 1 to START or 0 to GIVE UP:  \n"
                )
                await asyncio.sleep(TEMPO)
                if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                    self.bot.game = False
                    log.info("Encerrando jogo")
                    return
                playerState = int(most_common(self.bot.acoes))
                self.bot.acoes = []

            # cheats and easter eggs
            if playerState == 99:
                # cheat mode
                await ctx.send(
                    "\n     *G*O*D*\n \n    *M*O*D*E*\n \n *E*N*A*B*L*E*D*\n"
                )
                playerATK = 99
                playerDEF = 99
            elif playerState == 69:
                # easter egg 1
                await ctx.send("\n   *N*I*C*E*!*\n")
            elif playerState == 24:
                # easter egg 2
                await ctx.send("\n   *G*A*Y*!*\n")

            # GAMEPLAY HAPPENS HERE
            if playerState != 0:
                # EMPTY ROOM
                if roomGen == 1:
                    action = 0
                    await ctx.send(
                        "\n You enter the "
                        + roomAdjective
                        + " room"
                        + " The room is empty"
                    )

                    # await ctx.send("       |_ _       _  _           ")
                    # await ctx.send("       | _ _   _|     _ _        ")
                    # await ctx.send("     | | |    _ _     _ _        ")
                    # await ctx.send("    /  |   _   _ |  _            ")
                    # await ctx.send("   |   |_ _	_ _       |_ _      ")
                    # await ctx.send("   /   |    _|    _      _ _     ")
                    # await ctx.send("       |_ _ _ _ _ _ _ _ _ _ _    ")
                    # await ctx.send("   /  /  ~.  .  ^   .    . ^     ")
                    # await ctx.send("   | / . . .   ,    ^~   .  .    ")
                    # await ctx.send("    /  . ^ , ~     .  ^ .     .  ")
                    # await ctx.send("  |/  , . .     .      ^  .      ")
                    # await ctx.send("  / .  ^    .   .  ^   ,  . ~    ")

                    counter = counter + 1
                    while action != 1:
                        await ctx.send("\n-->Type 1 to continue  \n")
                        await asyncio.sleep(TEMPO)
                        if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                            self.bot.game = False
                            log.info("Encerrando jogo")
                            return
                        action = int(most_common(self.bot.acoes))
                        self.bot.acoes = []

                # ROOM WITH MONSTER
                elif roomGen == 2:
                    action = 0

                    await ctx.send(
                        "\n You enter the "
                        + roomAdjective
                        + " room"
                        + " The room has a "
                        + monsterAdjective
                        + " "
                        + monsterNAME
                    )

                    # await ctx.send("           ^_____^        ")
                    # await ctx.send("           0     0        ")
                    # await ctx.send("       WW  |  A  |        ")
                    # await ctx.send("       \ \ \_www_/        ")
                    # await ctx.send("        \ \__|+|___/^\    ")
                    # await ctx.send("         \___|+|___/\ \   ")
                    # await ctx.send("          ___|+|___  \ \  ")
                    # await ctx.send("          | |   | |   MM  ")
                    # await ctx.send("         /__|   |__\      ")

                    await ctx.send(
                        " The "
                        + monsterNAME
                        + " ATK is "
                        + str(monsterATK)
                        + " The "
                        + monsterNAME
                        + " DEF is "
                        + str(monsterDEF)
                        + "\n Your ATK is "
                        + str(playerATK)
                        + "\n Your DEF is "
                        + str(playerDEF)
                    )

                    # player decision
                    await ctx.send(
                        "\n-->Type 1 to attack \n-->Type other number to run away \n"
                    )

                    await asyncio.sleep(TEMPO)

                    if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                        self.bot.game = False
                        log.info("Encerrando jogo")
                        return
                    action = int(most_common(self.bot.acoes))
                    self.bot.acoes = []

                    if action != 1:
                        # RUN AWAY
                        await ctx.send("\n You ran away")
                        self.score -= 1
                        counter = counter + 1
                    else:
                        # COMBAT
                        diceP = randint(1, 6)
                        diceM = randint(1, 5)
                        await ctx.send("\n You rolled " + str(diceP))

                        if playerATK + diceP >= monsterDEF:
                            await ctx.send(" You killed the " + monsterNAME)
                            self.score += monsterSCORE
                            counter = counter + 1
                        elif monsterATK + diceM >= playerDEF:
                            await ctx.send(
                                " The " + monsterNAME + " rolled " + str(diceM)
                            )
                            await ctx.send(" The " + monsterNAME + " killed you")
                            self.score -= 1  #
                            counter = counter + 1
                            playerState = 0
                        else:
                            await ctx.send(
                                "\n The monster rolled "
                                + str(diceM)
                                + "\n You and the "
                                + monsterNAME
                                + " try to attack each other but can't"
                                + "\n You two end up having a pleasant conversation"
                            )
                            self.score += monsterSCORE
                            counter = counter + 1

                # ROOM WITH TRAP
                elif roomGen == 3:
                    action = 0
                    await ctx.send(
                        "\n You enter the "
                        + roomAdjective
                        + " room"
                        + "\n The room has a "
                        + trapAdjective
                        + " trap"
                    )

                    # await ctx.send("              .    .         .       ")
                    # await ctx.send("         .    ______________         ")
                    # await ctx.send("             /             / .       ")
                    # await ctx.send("          . /    trap     /          ")
                    # await ctx.send("           /             /   .       ")
                    # await ctx.send("          /_____________/ .          ")
                    # await ctx.send("           .       .      .          ")

                    await ctx.send(
                        " The trap ATK is "
                        + str(trapATK)
                        + "\n Your DEF "
                        + str(playerDEF)
                    )

                    # player decision
                    await ctx.send(
                        "\n-->Type 1 to disarm \n-->Type other number to avoid the trap \n"
                    )
                    await asyncio.sleep(TEMPO)

                    if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                        self.bot.game = False
                        log.info("Encerrando jogo")
                        return
                    action = int(most_common(self.bot.acoes))
                    self.bot.acoes = []

                    if action != 1:
                        await ctx.send("\n You avoided the trap")
                        self.score = self.score - 1
                        counter = counter + 1
                    else:
                        diceP = randint(1, 6)
                        await ctx.send("\n You rolled " + str(diceP))
                        if trapATK >= playerDEF + diceP:
                            await ctx.send(" You fell in the trap!")
                            self.score = self.score - 1
                            counter = counter + 1
                            playerState = 0
                        else:
                            await ctx.send("\n You disarmed the trap!")
                            self.score = self.score + 3
                            counter = counter + 1

                # CHEST ROOM
                elif roomGen == 4:
                    chest = randint(1, 6)  # generating chest
                    action = 0
                    await ctx.send(
                        "\n You enter the "
                        + roomAdjective
                        + " room"
                        + " The room has a chest"
                    )

                    # await ctx.send("         ____________         ")
                    # await ctx.send("        /           /|        ")
                    # await ctx.send("       /___________/ |        ")
                    # await ctx.send("       |     ?     | |        ")
                    # await ctx.send("       |    ? ?    | |        ")
                    # await ctx.send("       |     ?     | /        ")
                    # await ctx.send("       |___________|/         ")

                    # player decision
                    await ctx.send(
                        "\n-->Type 1 to open \n-->Type other number to proceed \n"
                    )

                    await asyncio.sleep(TEMPO)
                    if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                        self.bot.game = False
                        log.info("Encerrando jogo")
                        return
                    action = int(most_common(self.bot.acoes))
                    self.bot.acoes = []

                    if action != 1:
                        await ctx.send("\n You leave the closed chest behind \n")
                        counter = counter + 1
                    else:
                        await ctx.send("\n You opened the chest!")
                        counter = counter + 1

                        # coin
                        if chest == 1:
                            await ctx.send(" You found a single coin!")
                            self.score = self.score + 5

                        # gem
                        elif chest == 2:
                            await ctx.send(" You found a gem!")
                            self.score = self.score + 10

                        # potion
                        elif chest == 3:
                            action = 0
                            await ctx.send(
                                " You found a bottle with a mysterious liquid"
                            )
                            await ctx.send(" Do you wish to drink it?")

                            # player decision
                            await ctx.send(
                                "\n-->Type 1 to drink \n-->Type other number to proceed \n"
                            )

                            await asyncio.sleep(TEMPO)
                            if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                                self.bot.game = False
                                log.info("Encerrando jogo")
                                return
                            action = int(most_common(self.bot.acoes))
                            self.bot.acoes = []

                            if action != 1:
                                await ctx.send("\n You leave the bottle behind...")
                            else:
                                await ctx.send(
                                    "\n You drink the potion!\n You feel stronger!"
                                )
                                playerATK = playerATK + 2
                                self.score = self.score + 2
                                await ctx.send(
                                    " Your ATK was increased to " + str(playerATK)
                                )

                        # poison
                        elif chest == 4:
                            action = 0
                            await ctx.send(
                                " You found a bottle with a mysterious liquid!"
                            )
                            await ctx.send(" Do you wish to drink it?")

                            # player decision
                            await ctx.send(
                                "\n-->Type 1 to drink \n-->Type other number to proceed \n"
                            )

                            await asyncio.sleep(TEMPO)
                            if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                                self.bot.game = False
                                log.info("Encerrando jogo")
                                return
                            action = int(most_common(self.bot.acoes))
                            self.bot.acoes = []

                            if action != 1:
                                await ctx.send(" \nYou leave the bottle behind...")
                            else:
                                await ctx.send(
                                    " \nYou drink the POISON!\n You feel weakened!"
                                )
                                playerDEF = playerDEF - 2
                                self.score = self.score + 2
                                await ctx.send(
                                    " Your DEF was decreased to " + str(playerDEF)
                                )

                        # scroll
                        elif chest == 5:
                            action = 0
                            await ctx.send(
                                " You found a mysterious scroll!"
                                + "\n Do you wish to read it?"
                            )

                            # player decision
                            await ctx.send(
                                "\n-->Type 1 to read it \n-->Type other number to proceed \n"
                            )

                            await asyncio.sleep(TEMPO)
                            if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                                self.bot.game = False
                                log.info("Encerrando jogo")
                                return
                            action = int(most_common(self.bot.acoes))
                            self.bot.acoes = []

                            if action != 1:
                                await ctx.send("\n You leave the scroll behind...")
                            else:
                                await ctx.send(
                                    "\n You read the magic scroll!\n You feel enchanted!"
                                )
                                playerATK = playerATK + randint(1, 3)
                                playerDEF = playerDEF + randint(1, 3)
                                self.score = self.score + 2
                                await ctx.send(
                                    " Your ATK was increased to " + str(playerATK)
                                )
                                await ctx.send(
                                    " Your DEF was increased to " + str(playerDEF)
                                )

                        # empty chest
                        elif chest == 6:
                            await ctx.send(
                                " The chest was empty!\n Better luck next time... "
                            )

                # ZAP ROOM
                elif roomGen == 5:
                    if playerATK > 10 and playerDEF > 10 and counter > zapCount:
                        action = 0
                        await ctx.send(
                            "\n You enter the "
                            + roomAdjective
                            + " room"
                            + "\n The room appears to empty"
                        )

                        # await ctx.send("       |_ _       _  _           ")
                        # await ctx.send("       | _ _   _|     _ _        ")
                        # await ctx.send("     | | |    _ _     _ _        ")
                        # await ctx.send("    /  |   _   _ |  _            ")
                        # await ctx.send("   |   |_ _	_ _       |_ _      ")
                        # await ctx.send("   /   |    _|    _      _ _     ")
                        # await ctx.send("       |_ _ _ _ _ _ _ _ _ _ _    ")
                        # await ctx.send("   /  /  ~.  .  ^   .    . ^     ")
                        # await ctx.send("   | / . . .   ,    ^~   .  .    ")
                        # await ctx.send("    /  . ^ , ~     .  ^ .     .  ")
                        # await ctx.send("  |/  , . .     .      ^  .      ")
                        # await ctx.send("  / .  ^    .   .  ^   ,  . ~    ")

                        counter = counter + 1

                        while action != 1:
                            await ctx.send("\n-->Type 1 to continue  \n")

                            await asyncio.sleep(TEMPO)
                            if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                                self.bot.game = False
                                log.info("Encerrando jogo")
                                return
                            action = int(most_common(self.bot.acoes))
                            self.bot.acoes = []

                        await ctx.send("\n You was zapped by a mysterious energy!")
                        await ctx.send(" Your stats have been reset!")
                        playerATK = 1 + randint(1, 3)
                        playerDEF = 3 + randint(1, 3)
                    else:
                        action = 0
                        await ctx.send(
                            "\n You enter the "
                            + roomAdjective
                            + " room"
                            + "\n The room is empty"
                        )

                        # await ctx.send("       |_ _       _  _           ")
                        # await ctx.send("       | _ _   _|     _ _        ")
                        # await ctx.send("     | | |    _ _     _ _        ")
                        # await ctx.send("    /  |   _   _ |  _            ")
                        # await ctx.send("   |   |_ _	_ _       |_ _      ")
                        # await ctx.send("   /   |    _|    _      _ _     ")
                        # await ctx.send("       |_ _ _ _ _ _ _ _ _ _ _    ")
                        # await ctx.send("   /  /  ~.  .  ^   .    . ^     ")
                        # await ctx.send("   | / . . .   ,    ^~   .  .    ")
                        # await ctx.send("    /  . ^ , ~     .  ^ .     .  ")
                        # await ctx.send("  |/  , . .     .      ^  .      ")
                        # await ctx.send("  / .  ^    .   .  ^   ,  . ~    ")

                        counter = counter + 1

                        while action != 1:
                            await ctx.send("\n-->Type 1 to continue  \n")

                            await asyncio.sleep(TEMPO)
                            if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                                self.bot.game = False
                                log.info("Encerrando jogo")
                                return
                            action = int(most_common(self.bot.acoes))
                            self.bot.acoes = []

            # GAME OVER MESSAGES

            if self.score < 0 and playerState == 0:
                # for negative score
                await ctx.send(
                    "\n YOU ARE DEAD!"
                    + "\n YOUR SCORE WAS negative "
                    + str(self.score * -1)
                    + "\n *Y*O*U***S*U*C*K*\n"
                )

                # try again or quit
                await ctx.send("\n Do you wish to try again?\n")

                # player decision
                await ctx.send("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n")

                await asyncio.sleep(TEMPO)
                if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                    self.bot.game = False
                    log.info("Encerrando jogo")
                    return
                action = int(most_common(self.bot.acoes))
                self.bot.acoes = []

                if action == 1:
                    playerState = 1
                    playerATK = 1 + randint(1, 3)
                    playerDEF = 3 + randint(1, 3)
                    counter = 0
                    self.score = 0
                else:
                    playerState = 0

            elif self.score >= 100 and playerState != 0:
                # for WINNER
                await ctx.send(
                    "\n YOU'RE WINNER!"
                    + " YOUR SCORE WAS "
                    + str(self.score)
                    + "\n *C*O*N*G*R*A*T*U*L*A*T*I*O*N*S*\n"
                    + " You escaped the Crappy Dungeon!\n"
                )

                # try again or quit
                await ctx.send("\n Do you wish to try again?\n")

                # player decision
                await ctx.send("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n")

                await asyncio.sleep(TEMPO)
                if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                    self.bot.game = False
                    log.info("Encerrando jogo")
                    return
                action = int(most_common(self.bot.acoes))
                self.bot.acoes = []

                if action == 1:
                    playerState = 1
                    playerATK = 1 + randint(1, 3)
                    playerDEF = 3 + randint(1, 3)
                    counter = 0
                    self.score = 0
                else:
                    playerState = 0

            elif (
                self.score >= 100
                and playerState != 0
                and (playerATK > 90 or playerDEF > 90)
            ):
                # for CHEATERS
                await ctx.send(
                    "\n YOU'RE A:"
                    + "\n *C*H*E*A*T*E*R*\n"
                    + " YOUR SCORE WAS ZERO"
                    + " Cheaters NEVER win!\n"
                )

                # try again or quit
                await ctx.send("\n Do you wish to try again?\n")

                # player decision
                await ctx.send("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n")

                await asyncio.sleep(TEMPO)
                if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                    self.bot.game = False
                    log.info("Encerrando jogo")
                    return
                action = int(most_common(self.bot.acoes))
                self.bot.acoes = []

                if action == 1:
                    playerState = 1
                    playerATK = 1 + randint(1, 3)
                    playerDEF = 3 + randint(1, 3)
                    counter = 0
                    self.score = 0
                else:
                    playerState = 0

            elif playerState == 0:
                # regular message
                await ctx.send(
                    "\n YOU ARE DEAD!"
                    + " YOUR SCORE WAS "
                    + str(self.score)
                    + "\n *G*A*M*E***O*V*E*R*\n"
                )

                # try again or quit
                await ctx.send("\n Do you wish to try again?\n")

                # player decision
                await ctx.send("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n")

                await asyncio.sleep(TEMPO)
                if not (self.bot.acoes) or ("stop" in self.bot.acoes):
                    self.bot.game = False
                    log.info("Encerrando jogo")
                    return
                action = int(most_common(self.bot.acoes))
                self.bot.acoes = []

                if action == 1:
                    playerState = 1
                    playerATK = 1 + randint(1, 3)
                    playerDEF = 3 + randint(1, 3)
                    counter = 0
                    self.score = 0
                else:
                    playerState = 0


async def setup(bot):
    """Adiciona cog ao bot"""
    await bot.add_cog(Games(bot))
