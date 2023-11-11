# import modules etc

from random import randint

# sets counters and score

playerState = 1  # 1 == ALIVE, 0 == DEAD
score = 0
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

# generates player states
playerATK = 1 + randint(1, 3)
playerDEF = 3 + randint(1, 3)

# title screen start


def title(ctx):
    ctx.message.send("  #### ####   ###  ####  ####  #     # ")
    ctx.message.send(" #     #   # #   # #   # #   #  #   #  ")
    ctx.message.send(" #     ####  ##### #   # #   #   # #   ")
    ctx.message.send(" #     # #   #   # ####  ####     #    ")
    ctx.message.send("  #### #  #  #   # #     #        #    ")

    ctx.message.send("")

    ctx.message.send("    ####  #   # #   #  ####  ####  ####  #   # ")
    ctx.message.send("    #   # #   # ##  # #      #    #    # ##  # ")
    ctx.message.send("    #   # #   # # # # #  ### ###  #    # # # # ")
    ctx.message.send("    #   # #   # #  ## #    # #    #    # #  ## ")
    ctx.message.send("    ####   ###  #   #  ####  ####  ####  #   # ")

    ctx.message.send("")

    ctx.message.send("         #### ####   ###  #    #    # #     #### ####  ")
    ctx.message.send("        #     #   # #   # #    #    # #     #    #   # ")
    ctx.message.send("        #     ####  #####  #  # #  #  #     ###  ####  ")
    ctx.message.send("        #     # #   #   #   # # # #   #     #    # #   ")
    ctx.message.send("         #### #  #  #   #    #   #    ##### #### #  #  ")

    ctx.message.send(
        " \n -> Welcome to Crappy Dungeon Crawler v1.2 for *P*Y*T*H*O*N*!* <- \n"
    )
    ctx.message.send(
        " Follow the instructions on the screen and type your commands to play"
    )
    ctx.message.send(
        " Kill monsters, disarm traps and collect coins and gems to increase your SCORE"
    )
    ctx.message.send(" Get a *100* SCORE to *W*I*N*!!")


# title screen end


# main loop
def jogada(ctx, acao):
    global playerState
    global playerATK
    global playerDEF
    global counter
    global score

    while playerState != 0 and score < 100:
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
            ctx.message.send("\n ATTENTION! \n Things will get harder!\n")
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
            ctx.message.send(
                "\n Your ATK is " + str(playerATK) + " | Your DEF is " + str(playerDEF)
            )
            ctx.message.send(" Your score is " + str(score))
            ctx.message.send(" You made " + str(counter) + " moves")
            playerState = int(input("\n-->Type 1 to START or 0 to GIVE UP:  \n"))
        # or continue text
        else:
            ctx.message.send("\n Your score is " + str(score))
            ctx.message.send(" You made " + str(counter) + " moves ")
            playerState = int(input("\n-->Type 1 to CONTINUE or 0 to GIVE UP:  \n"))

        # cheats and easter eggs
        if playerState == 99:
            # cheat mode
            ctx.message.send("\n     *G*O*D*\n \n    *M*O*D*E*\n \n *E*N*A*B*L*E*D*\n")
            playerATK = 99
            playerDEF = 99
        elif playerState == 69:
            # easter egg 1
            ctx.message.send("\n   *N*I*C*E*!*\n")
        elif playerState == 24:
            # easter egg 2
            ctx.message.send("\n   *G*A*Y*!*\n")

        # GAMEPLAY HAPPENS HERE
        if playerState != 0:
            # EMPTY ROOM
            if roomGen == 1:
                action = 0
                ctx.message.send("\n You enter the " + roomAdjective + " room")
                ctx.message.send(" The room is empty")
                ctx.message.send("")
                ctx.message.send("       |_ _       _  _           ")
                ctx.message.send("       | _ _   _|     _ _        ")
                ctx.message.send("     | | |    _ _     _ _        ")
                ctx.message.send("    /  |   _   _ |  _            ")
                ctx.message.send("   |   |_ _	_ _       |_ _      ")
                ctx.message.send("   /   |    _|    _      _ _     ")
                ctx.message.send("       |_ _ _ _ _ _ _ _ _ _ _    ")
                ctx.message.send("   /  /  ~.  .  ^   .    . ^     ")
                ctx.message.send("   | / . . .   ,    ^~   .  .    ")
                ctx.message.send("    /  . ^ , ~     .  ^ .     .  ")
                ctx.message.send("  |/  , . .     .      ^  .      ")
                ctx.message.send("  / .  ^    .   .  ^   ,  . ~    ")
                ctx.message.send("")
                counter = counter + 1
                while action != 1:
                    action = int(input("\n-->Type 1 to continue  \n"))

            # ROOM WITH MONSTER
            elif roomGen == 2:
                action = 0

                ctx.message.send("\n You enter the " + roomAdjective + " room")
                ctx.message.send(
                    " The room has a " + monsterAdjective + " " + monsterNAME
                )
                ctx.message.send("")
                ctx.message.send("           ^_____^        ")
                ctx.message.send("           0     0        ")
                ctx.message.send("       WW  |  A  |        ")
                ctx.message.send("       \ \ \_www_/        ")
                ctx.message.send("        \ \__|+|___/^\    ")
                ctx.message.send("         \___|+|___/\ \   ")
                ctx.message.send("          ___|+|___  \ \  ")
                ctx.message.send("          | |   | |   MM  ")
                ctx.message.send("         /__|   |__\      ")
                ctx.message.send("")

                ctx.message.send("")
                ctx.message.send(" The " + monsterNAME + " ATK is " + str(monsterATK))
                ctx.message.send(" The " + monsterNAME + " DEF is " + str(monsterDEF))
                ctx.message.send("")
                ctx.message.send(" Your ATK is " + str(playerATK))
                ctx.message.send(" Your DEF is " + str(playerDEF))

                # player decision
                # time.sleep(TEMPO)
                # if not self.bot.acoes:
                #   self.bot.game = FALSE
                #   return
                # jogada = most_common(self.bot.acoes)
                # self.bot.acoes = []
                action = int(
                    input("\n-->Type 1 to attack \n-->Type other number to run away \n")
                )

                if action != 1:
                    # RUN AWAY
                    ctx.message.send("\n You ran away")
                    score = score - 1
                    counter = counter + 1
                else:
                    # COMBAT
                    diceP = randint(1, 6)
                    diceM = randint(1, 5)
                    ctx.message.send("\n You rolled " + str(diceP))

                    if playerATK + diceP >= monsterDEF:
                        ctx.message.send(" You killed the " + monsterNAME)
                        score = score + monsterSCORE
                        counter = counter + 1
                    elif monsterATK + diceM >= playerDEF:
                        ctx.message.send(
                            " The " + monsterNAME + " rolled " + str(diceM)
                        )
                        ctx.message.send(" The " + monsterNAME + " killed you")
                        score = score - 1
                        counter = counter + 1
                        playerState = 0
                    else:
                        ctx.message.send("\n The monster rolled " + str(diceM))
                        ctx.message.send(
                            " You and the "
                            + monsterNAME
                            + " try to attack each other but can't"
                        )
                        ctx.message.send(
                            " You two end up having a pleasant conversation"
                        )
                        score = score + monsterSCORE
                        counter = counter + 1

            # ROOM WITH TRAP
            elif roomGen == 3:
                action = 0
                ctx.message.send("\n You enter the " + roomAdjective + " room")
                ctx.message.send(" The room has a " + trapAdjective + " trap")
                ctx.message.send("")
                ctx.message.send("              .    .         .       ")
                ctx.message.send("         .    ______________         ")
                ctx.message.send("             /             / .       ")
                ctx.message.send("          . /    trap     /          ")
                ctx.message.send("           /             /   .       ")
                ctx.message.send("          /_____________/ .          ")
                ctx.message.send("           .       .      .          ")
                ctx.message.send("")
                ctx.message.send(" The trap ATK is " + str(trapATK))
                ctx.message.send(" Your DEF " + str(playerDEF))

                # player decision
                action = int(
                    input(
                        "\n-->Type 1 to disarm \n-->Type other number to avoid the trap \n"
                    )
                )

                if action != 1:
                    ctx.message.send("\n You avoided the trap")
                    score = score - 1
                    counter = counter + 1
                else:
                    diceP = randint(1, 6)
                    ctx.message.send("\n You rolled " + str(diceP))
                    if trapATK >= playerDEF + diceP:
                        ctx.message.send(" You fell in the trap!")
                        score = score - 1
                        counter = counter + 1
                        playerState = 0
                    else:
                        ctx.message.send("\n You disarmed the trap!")
                        score = score + 3
                        counter = counter + 1

            # CHEST ROOM
            elif roomGen == 4:
                chest = randint(1, 6)  # generating chest
                action = 0
                ctx.message.send("\n You enter the " + roomAdjective + " room")
                ctx.message.send(" The room has a chest")
                ctx.message.send("")
                ctx.message.send("         ____________         ")
                ctx.message.send("        /           /|        ")
                ctx.message.send("       /___________/ |        ")
                ctx.message.send("       |     ?     | |        ")
                ctx.message.send("       |    ? ?    | |        ")
                ctx.message.send("       |     ?     | /        ")
                ctx.message.send("       |___________|/         ")
                ctx.message.send("")

                # player decision
                action = int(
                    input("\n-->Type 1 to open \n-->Type other number to proceed \n")
                )

                if action != 1:
                    ctx.message.send("\n You leave the closed chest behind \n")
                    counter = counter + 1
                else:
                    ctx.message.send("\n You opened the chest!")
                    counter = counter + 1

                    # coin
                    if chest == 1:
                        ctx.message.send(" You found a single coin!")
                        score = score + 5

                    # gem
                    elif chest == 2:
                        ctx.message.send(" You found a gem!")
                        score = score + 10

                    # potion
                    elif chest == 3:
                        action = 0
                        ctx.message.send(" You found a bottle with a mysterious liquid")
                        ctx.message.send(" Do you wish to drink it?")

                        # player decision
                        action = int(
                            input(
                                "\n-->Type 1 to drink \n-->Type other number to proceed \n"
                            )
                        )

                        if action != 1:
                            ctx.message.send("\n You leave the bottle behind...")
                        else:
                            ctx.message.send(
                                "\n You drink the potion!\n You feel stronger!"
                            )
                            playerATK = playerATK + 2
                            score = score + 2
                            ctx.message.send(
                                " Your ATK was increased to " + str(playerATK)
                            )

                    # poison
                    elif chest == 4:
                        action = 0
                        ctx.message.send(
                            " You found a bottle with a mysterious liquid!"
                        )
                        ctx.message.send(" Do you wish to drink it?")

                        # player decision
                        action = int(
                            input(
                                "\n-->Type 1 to drink \n-->Type other number to proceed \n"
                            )
                        )

                        if action != 1:
                            ctx.message.send(" \nYou leave the bottle behind...")
                        else:
                            ctx.message.send(
                                " \nYou drink the POISON!\n You feel weakened!"
                            )
                            playerDEF = playerDEF - 2
                            score = score + 2
                            ctx.message.send(
                                " Your DEF was decreased to " + str(playerDEF)
                            )

                    # scroll
                    elif chest == 5:
                        action = 0
                        ctx.message.send(" You found a mysterious scroll!")
                        ctx.message.send(" Do you wish to read it?")

                        # player decision
                        action = int(
                            input(
                                "\n-->Type 1 to read it \n-->Type other number to proceed \n"
                            )
                        )

                        if action != 1:
                            ctx.message.send("\n You leave the scroll behind...")
                        else:
                            ctx.message.send(
                                "\n You read the magic scroll!\n You feel enchanted!"
                            )
                            playerATK = playerATK + randint(1, 3)
                            playerDEF = playerDEF + randint(1, 3)
                            score = score + 2
                            ctx.message.send(
                                " Your ATK was increased to " + str(playerATK)
                            )
                            ctx.message.send(
                                " Your DEF was increased to " + str(playerDEF)
                            )

                    # empty chest
                    elif chest == 6:
                        ctx.message.send(
                            " The chest was empty!\n Better luck next time... "
                        )

            # ZAP ROOM
            elif roomGen == 5:
                if playerATK > 10 and playerDEF > 10 and counter > zapCount:
                    action = 0
                    ctx.message.send("\n You enter the " + roomAdjective + " room")
                    ctx.message.send(" The room appears to empty")
                    ctx.message.send("")
                    ctx.message.send("       |_ _       _  _           ")
                    ctx.message.send("       | _ _   _|     _ _        ")
                    ctx.message.send("     | | |    _ _     _ _        ")
                    ctx.message.send("    /  |   _   _ |  _            ")
                    ctx.message.send("   |   |_ _	_ _       |_ _      ")
                    ctx.message.send("   /   |    _|    _      _ _     ")
                    ctx.message.send("       |_ _ _ _ _ _ _ _ _ _ _    ")
                    ctx.message.send("   /  /  ~.  .  ^   .    . ^     ")
                    ctx.message.send("   | / . . .   ,    ^~   .  .    ")
                    ctx.message.send("    /  . ^ , ~     .  ^ .     .  ")
                    ctx.message.send("  |/  , . .     .      ^  .      ")
                    ctx.message.send("  / .  ^    .   .  ^   ,  . ~    ")
                    ctx.message.send("")
                    counter = counter + 1

                    while action != 1:
                        action = int(input("\n-->Type 1 to continue  \n"))

                    ctx.message.send("\n You was zapped by a mysterious energy!")
                    ctx.message.send(" Your stats have been reset!")
                    playerATK = 1 + randint(1, 3)
                    playerDEF = 3 + randint(1, 3)
                else:
                    action = 0
                    ctx.message.send("\n You enter the " + roomAdjective + " room")
                    ctx.message.send(" The room is empty")
                    ctx.message.send("")
                    ctx.message.send("       |_ _       _  _           ")
                    ctx.message.send("       | _ _   _|     _ _        ")
                    ctx.message.send("     | | |    _ _     _ _        ")
                    ctx.message.send("    /  |   _   _ |  _            ")
                    ctx.message.send("   |   |_ _	_ _       |_ _      ")
                    ctx.message.send("   /   |    _|    _      _ _     ")
                    ctx.message.send("       |_ _ _ _ _ _ _ _ _ _ _    ")
                    ctx.message.send("   /  /  ~.  .  ^   .    . ^     ")
                    ctx.message.send("   | / . . .   ,    ^~   .  .    ")
                    ctx.message.send("    /  . ^ , ~     .  ^ .     .  ")
                    ctx.message.send("  |/  , . .     .      ^  .      ")
                    ctx.message.send("  / .  ^    .   .  ^   ,  . ~    ")
                    ctx.message.send("")
                    counter = counter + 1

                    while action != 1:
                        action = int(input("\n-->Type 1 to continue  \n"))

        # GAME OVER MESSAGES

        if score < 0 and playerState == 0:
            # for negative score
            ctx.message.send("\n YOU ARE DEAD!")
            ctx.message.send(" YOUR SCORE WAS negative " + str(score * -1))
            ctx.message.send("\n *Y*O*U***S*U*C*K*\n")
            ctx.message.send("")

            # try again or quit
            ctx.message.send("\n Do you wish to try again?\n")

            # player decision
            action = int(input("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n"))

            if action == 1:
                playerState = 1
                playerATK = 1 + randint(1, 3)
                playerDEF = 3 + randint(1, 3)
                counter = 0
                score = 0
            else:
                playerState = 0

        elif score >= 100 and playerState != 0:
            # for WINNER
            ctx.message.send("\n YOU'RE WINNER!")
            ctx.message.send(" YOUR SCORE WAS " + str(score))
            ctx.message.send("\n *C*O*N*G*R*A*T*U*L*A*T*I*O*N*S*\n")
            ctx.message.send(" You escaped the Crappy Dungeon!\n")

            # try again or quit
            ctx.message.send("\n Do you wish to try again?\n")

            # player decision
            action = int(input("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n"))

            if action == 1:
                playerState = 1
                playerATK = 1 + randint(1, 3)
                playerDEF = 3 + randint(1, 3)
                counter = 0
                score = 0
            else:
                playerState = 0

        elif score >= 100 and playerState != 0 and (playerATK > 90 or playerDEF > 90):
            # for CHEATERS
            ctx.message.send("\n YOU'RE A:")
            ctx.message.send("\n *C*H*E*A*T*E*R*\n")
            ctx.message.send(" YOUR SCORE WAS ZERO")
            ctx.message.send(" Cheaters NEVER win!\n")

            # try again or quit
            ctx.message.send("\n Do you wish to try again?\n")

            # player decision
            action = int(input("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n"))

            if action == 1:
                playerState = 1
                playerATK = 1 + randint(1, 3)
                playerDEF = 3 + randint(1, 3)
                counter = 0
                score = 0
            else:
                playerState = 0

        elif playerState == 0:
            # regular message
            ctx.message.send("\n YOU ARE DEAD!")
            ctx.message.send(" YOUR SCORE WAS " + str(score))
            ctx.message.send("\n *G*A*M*E***O*V*E*R*\n")

            # try again or quit
            ctx.message.send("\n Do you wish to try again?\n")

            # player decision
            action = int(input("\n-->Type 1 to TRY AGAIN or 0 to GIVE UP:  \n"))

            if action == 1:
                playerState = 1
                playerATK = 1 + randint(1, 3)
                playerDEF = 3 + randint(1, 3)
                counter = 0
                score = 0
            else:
                playerState = 0
