import pandas as pd
import numpy as np
import os

def parseGames(path):

    games = []

    allLines = []
    breaks = []
    with open(path,'r') as txt:
        for i,line in enumerate(txt):
            allLines.append(line)

            if line == '\n':
                breaks.append(i)

    # parse individual games

    games = []

    curr = 0
    for i in breaks:
        games.append(allLines[curr:i])
        curr = i+1

    return games  

def getGameId(game):
    gameIdLine = [a for a in game if 'Game ID' in a][0]
    gameIdCode = gameIdLine.split()[2]
    # gameIdStakes = gameIdLine.split()[3].replace('.','_').replace('/','-')

    # gameIdFinal = '{}_{}'.format(gameIdCode,gameIdStakes)

    return gameIdCode

def grabInsideBrackets(aString):
    return aString.split('[', 1)[1].split(']')[0]

def grabInsideParens(aString):
    return aString.split('(', 1)[1].split(')')[0]


def reformatCards(aString):

    changeDict = {
        'J':'11',
        'Q':'12',
        'K':'13',
        'A':'14'
    }

    suit = aString[-1]
    num = aString[:-1]

    if num in list(changeDict.keys()):
        num = changeDict[num]

    new = suit.upper() + num

    return new

def getUniquePlayers(game):
    players = {}
    # find the players that have revealed hole cards, this will either be the person playing or someone at the end 
    raw = [a for a in game if 'Player' in a and '[' in a]

    # determine the default player, his hole cards are shown through two different lines so it will be the non unique name
    playerNames = [a.split()[1] for a in raw]
    # for p in playerNames:
    #     if playerNames.count(p) == 2:
    #         playerPlayer = p

    playerPlayer = 'IlxxxlI' 
    # in the case that the person also shows their cards, remove that record and rely on the dealing part of the data pipeline
    raw = [a for a in raw if '{} shows'.format(playerPlayer) not in a]

    pPlayerCards = [grabInsideBrackets(a) for a in raw if playerPlayer in a]

    # add player player to the players dict
    players[playerPlayer] = pPlayerCards

    # get other two 
    for p in playerNames:
        if p != playerPlayer:
            holeStr = [a for a in raw if p in a][0]
            holeCards = grabInsideBrackets(holeStr).split()

            players[p] = holeCards

    # reformat to correct card format
    players = {p : [reformatCards(a) for a in players[p]] for p in list(players.keys())}

    return players

def getCommunityCards(game):
    
    res = []
    
    for r in ['FLOP','TURN','RIVER']:

        # check if round occurred, if so return cards
        flops = [a for a in game if '***' in a and r in a]
        if len(flops) == 0:
            res.append([])
        else:
            # flopCardsRaw = grabInsideBrackets(flops[0]).split()
            flopCardsRaw = flops[0]
            if flopCardsRaw.count(']') == 2: # more than one bracket
                flopCardsRaw = flopCardsRaw[flopCardsRaw.find(']')+1:]
            flopReformat = grabInsideBrackets(flopCardsRaw).split()
            flopCards = [reformatCards(a) for a in flopReformat]
            res.append(flopCards)

    tupRes = tuple(res)

    return tupRes

def getRoundIndexes(game):
    # get max i where 'recieved' is mentioned at start of hole round, this is preflop betting on hole cards
    holeStart = max([i for (i,s) in enumerate(game) if 'Player' in s and 'received' in s])

    res = [holeStart]

    # for each round find the starting index if one exists

    for round in ['FLOP','TURN','RIVER']:
        raw = [i for (i,s) in enumerate(game) if '***' in s and round in s]
        if len(raw) != 0:
            res.append(max(raw))

    res.append(game.index('------ Summary ------\n')) # every game has this

    return res

def getBlinds(game):
    raw = [a for a in game if 'Player' in a and 'blind' in a]

    bigRaw = [a for a in raw if 'big' in a][0]
    smallRaw = [a for a in raw if 'small' in a][0]

    big = (bigRaw.split()[1],pd.to_numeric(grabInsideParens(bigRaw)))
    small = (smallRaw.split()[1],pd.to_numeric(grabInsideParens(smallRaw)))

    # create a tuple for each one that is tuple[0] player and tuple[1] int of big blind of small blind

    return big, small

def constructDataframe(players,game,winner,flop,turn,river,gameId):

    # get the indexes of the rounds in the game list, so each index is the round start, hole, flop, turn, river
    roundIxs = getRoundIndexes(game)

    bigBlind,smallBlind = getBlinds(game)

    master = pd.DataFrame()

    for player in list(players.keys()):
        # for each player that has hold cards shown, get their total bankroll
        bankRollRaw = [a for a in game if player in a and '(' in a][0]
        bankRoll = pd.to_numeric(grabInsideParens(bankRollRaw))

        # for each round, get the total sum of their bets and express 
        bets = []
        for i in range(1,len(roundIxs)):

            raw = [s for (ix,s) in enumerate(game) if player in s and '(' in s and ix > roundIxs[i-1] and ix < roundIxs[i]]

            if raw == []:
                bets.append(np.nan)

            else:
                # get the integer values of all the values
                nums = [pd.to_numeric(grabInsideParens(s)) for s in raw]
                sumBets = sum(nums)

                bets.append(sumBets)

        # get all-in binary and fold binary 
        allInsRaw = [a for a in game if 'allin' in a and player in a]
        foldRaw = [a for a in game if 'fold' in a and player in a]

        allInBins = [0 for _ in range(0,4)]
        foldBins = [0 for _ in range(0,4)]

        if len(allInsRaw) != 0:
            allInIx = game.index(allInsRaw[0])
            allInBins = [1 if roundIxs[i-1] < allInIx < roundIxs[i] else 0 for i in range(1,len(roundIxs))]

        if len(foldRaw) != 0:
            foldIx = game.index(foldRaw[0])
            foldBins = [1 if roundIxs[i-1] < foldIx < roundIxs[i] else 0 for i in range(1,len(roundIxs))]

        # make binary based on winner of the game
        winBin = 0
        if winner == player:
            winBin += 1

        # binary based on big and little blind
        bigBlindBin = 1 if bigBlind[0] == player else 0
        smallBlindBin = 1 if smallBlind[0] == player else 0

        # make cards list
        cardsDealt = [players[player],flop,turn,river]

        # make list same len as total num rounds
        newBets = bets + [0 for a in range(0,4-len(bets))]
        foldBins = foldBins + [0 for a in range(0,4-len(foldBins))]
        allInBins = allInBins + [0 for a in range(0,4-len(allInBins))]

        # convert to dataframe

        pdf = pd.DataFrame({
            'round':['hole','flop','turn','river'],
            'betDollar':newBets,
            'gameWinner':winBin,
            'allIn':allInBins,
            'fold':foldBins,
            'cards':cardsDealt
        })

        pdf['bankroll'] = bankRoll
        pdf['betPercent'] = pdf['betDollar'] / pdf['bankroll']
        pdf['gameId'] = gameId
        pdf['playerName'] = player

        # stuff for blinds
        pdf['isBigBlind'] = bigBlindBin
        pdf['isSmallBlind'] = smallBlindBin

        pdf['bigBlind'] = bigBlind[1]
        pdf['smallBlind'] = smallBlind[1]

        pdf = pdf.set_index(['gameId','playerName','round'],drop=True)

        master = master.append(pdf)

    master = master.fillna(0)

    return master

def getGameWinner(game):
    winStr = [a for a in game if 'Player' in a and '*' in a][0]
    winner = winStr.split()[1]
    return winner


def analyzeGame(game):
    # this takes a list that is strings of a single game

    # pull out game id
    gameId = getGameId(game)

    # pull unique players that have hole cards
    players = getUniquePlayers(game)

    # pull community cards (rounds are flop,turn,river)
    flop,turn,river = getCommunityCards(game)

    # back into who the winner is
    winner = getGameWinner(game)

    # pull bets from each player
    output = constructDataframe(players,game,winner,flop,turn,river,gameId)

    return output




# path = os.path.join('C:\\Users','templ','Documents','GitHub','gambling','texasHoldEm','game_data','Export Holdem Manager 2.0 12302016144830.txt')

# t = parseGames(path)

# # test = analyzeGame(t[2]) # this works fine

# test = analyzeGame(t[9])

# # import time
# # start = time.time()
# # test = analyzeGame(t[2])
# # end = time.time()
# # print("Elapsed time = %s" % (end - start))

# print('complete')

