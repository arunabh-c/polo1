import io, sys, time, datetime, urllib2, json, numpy, os

from poloniex import Poloniex
from ConfigParser import SafeConfigParser
from Logger import Logger
from decimal import *

SATOSHI = Decimal(10) ** -8

config = SafeConfigParser()
config_location = 'default.cfg'

defaultconfig =\
"""
[API]
apikey = YourAPIKey
secret = YourSecret

[BOT]
#sleep between iterations, time in seconds
sleeptime = 300
#minimum daily lend rate in percent
mindailyrate = 0.01
#max rate. 2% is good choice because it's default at margin trader interface. 5% is max to be accepted by the exchange
maxdailyrate = 2
#The number of offers to split the available balance uniformly across the [gaptop, gapbottom] range.
spreadlend = 3
#The depth of lendbook (in percent of lendable balance) to move through before placing the first (gapbottom) and last (gaptop) offer.
#if gapbottom is set to 0, the first offer will be at the lowest possible rate. However some low value is recommended (say 10%) to skip dust offers
gapbottom = 1
gaptop = 100
#Daily lend rate threshold after which we offer lends for 60 days as opposed to 2. If set to 0 all offers will be placed for a 2 day period
sixtydaythreshold = 0.2
# AutoRenew - if set to 1 the bot will toggle the AutoRenew flag for the loans when you stop it (Ctrl+C) and clear the AutoRenew flag when started
autorenew = 0
#custom config per coin, useful when closing positions etc.
#syntax: [COIN:mindailyrate:maxactiveamount, ... COIN:mindailyrate:maxactiveamount]
#if maxactive amount is 0 - stop lending this coin. in the future you'll be able to limit amount to be lent.
#coinconfig = ["BTC:0.18:1","CLAM:0.6:1"]
"""

loadedFiles = config.read([config_location])
#Create default config file if not found
if len(loadedFiles) != 1:
	config.readfp(io.BytesIO(defaultconfig))
	with open(config_location, "w") as configfile:
		configfile.write(defaultconfig)
		print 'Edit default.cfg file with your api key and secret values'
		exit(0)


sleepTime = float(config.get("BOT","sleeptime"))
minDailyRate = Decimal(config.get("BOT","mindailyrate"))/100
maxDailyRate = Decimal(config.get("BOT","maxdailyrate"))/100
spreadLend = int(config.get("BOT","spreadlend"))
gapBottom = Decimal(config.get("BOT","gapbottom"))
gapTop = Decimal(config.get("BOT","gaptop"))
sixtyDayThreshold = float(config.get("BOT","sixtydaythreshold"))/100
autorenew = int(config.get("BOT","autorenew"))

try:
	coincfg = {} #parsed
	coinconfig = (json.loads(config.get("BOT","coinconfig")))
	#coinconfig parser
	for cur in coinconfig:
		cur = cur.split(':')
		coincfg[cur[0]] = dict(minrate=(Decimal(cur[1]))/100, maxactive=Decimal(cur[2]))
except Exception as e:
	pass
	
#sanity checks
if sleepTime < 1 or sleepTime > 3600:
	print "sleeptime value must be 1-3600"
	exit(1)
if minDailyRate < 0.000003 or minDailyRate > 0.05: # 0.0003% daily is 1% yearly
	print "mindaily rate is set too low or too high, must be 0.0003-5%"
	exit(1)
if maxDailyRate < 0.000003 or maxDailyRate > 0.05:
	print "maxdaily rate is set too low or too high, must be 0.0003-5%"
	exit(1)
if spreadLend < 1 or spreadLend > 20:
	print "spreadlend value must be 1-20 range"
	exit(1)

dryRun = False
try:
	if sys.argv.index('--dryrun') > 0:
		dryRun = True
except ValueError:
	pass

def timestamp():
	ts = time.time()
	return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

bot = Poloniex(config.get("API","apikey"), config.get("API","secret"))
log = Logger()

#total lended global variable
totalLended = {}

def tradingbot():
    i=0
    data=[]
    old_data=[]
    max_change = numpy.zeros((1,5))#0:index 1:score 2:change
    ticker = bot.returnTicker()
    #crypto_pair = ticker.keys()
    with open('seedfile.txt', 'r') as seedfile:
         seed_data = json.load(seedfile)
    if os.stat('price_tickr.txt').st_size != 0:
       with open('price_tickr.txt') as infile:
            old_data = json.load(infile)
            for ticker_item in ticker.values():
              change = Decimal(0)
              match_index = Decimal(0)  
              if ticker_item['isFrozen'] != str(1):# and   #and (ticker.keys()[i] != 'USDT_XMR')
                #print (str(ticker_item['last']) + " " + old_data[i]['last_price'])
                if Decimal(old_data[i]['last_price'].encode("utf-8")) > Decimal(0):
                   change = (Decimal(ticker_item['baseVolume'].encode("utf-8"))/Decimal(old_data[i]['last_price'].encode("utf-8")) - 1)
                else:
                   change = Decimal(1)                
                #print(timestamp() + " Currencies clearing first level are " + ticker.keys()[i] + " with change of " + str(change) + " old match is " + old_data[i]['name'] + " with change of " + str(old_data[i]['change-3']))   
                if (Decimal(change) > Decimal(0.0001) and Decimal(old_data[i]['change-3'].encode("utf-8")) < Decimal(0.0001)):#(change > Decimal(0.0001) and Decimal(old_data[i]['change-1'] > Decimal(0.0001))) or (Decimal(old_data[i]['change-1'] > Decimal(0.0001) and Decimal(old_data[i]['change-2']> Decimal(0.0001)))) or (change > Decimal(0.0001) and Decimal(old_data[i]['change-2']> Decimal(0.0001))):
                   #print(timestamp() + " First level is " + ticker.keys()[i] + " change is " + str(change) + " change-3 is " + str(old_data[i]['change-3']))   
                   if Decimal(old_data[i]['change-1'].encode("utf-8")) > Decimal(0.0001):
                      #print(timestamp() + " Second level top is " + ticker.keys()[i] + " change-1 is " + str(old_data[i]['change-1']))   
                      match_index = Decimal(1)  
                      if Decimal(old_data[i]['change-2'].encode("utf-8")) > Decimal(0.0001):
                         #print(timestamp() + " Third level top is " + ticker.keys()[i] + " change-2 is " + str(old_data[i]['change-2']))   
                         match_index = Decimal(2)  
                         avg_change = Decimal(1)*change - Decimal(1)*Decimal(old_data[i]['change-3'].encode("utf-8")) + Decimal(1)*Decimal(old_data[i]['change-1'].encode("utf-8")) + Decimal(1)*Decimal(old_data[i]['change-2'].encode("utf-8"))
                      else:
                         #print(timestamp() + " Third level bottom is " + ticker.keys()[i] + " change-2 is " + str(old_data[i]['change-2']))   
                         avg_change = Decimal(1)*change - Decimal(1)*Decimal(old_data[i]['change-3'].encode("utf-8")) + Decimal(1)*Decimal(old_data[i]['change-1'].encode("utf-8")) - Decimal(1)*Decimal(old_data[i]['change-2'].encode("utf-8"))
                   elif Decimal(old_data[i]['change-2'].encode("utf-8")) < Decimal(0.0001):
                         if Decimal(old_data[i]['change-2'].encode("utf-8")) < Decimal(0):
                            match_index = Decimal(1)  						 
                            #print(timestamp() + " Second level bottom is " + ticker.keys()[i] + " change-1 is " + str(old_data[i]['change-1']))   
                         avg_change = Decimal(1)*change - Decimal(1)*Decimal(old_data[i]['change-3'].encode("utf-8")) - Decimal(1)*Decimal(old_data[i]['change-1'].encode("utf-8")) - Decimal(1)*Decimal(old_data[i]['change-2'].encode("utf-8"))
                   else:
                        if Decimal(old_data[i]['change-2'].encode("utf-8")) > Decimal(0.0001):
                           avg_change = Decimal(change) - Decimal(old_data[i]['change-3'].encode("utf-8")) - Decimal(old_data[i]['change-1'].encode("utf-8")) + Decimal(old_data[i]['change-2'].encode("utf-8"))
                        else:
                           avg_change = Decimal(change) - Decimal(old_data[i]['change-3'].encode("utf-8")) - Decimal(old_data[i]['change-1'].encode("utf-8")) - Decimal(old_data[i]['change-2'].encode("utf-8"))						   						
				   #avg_change = Decimal(0.3333)*change + Decimal(0.3333)*Decimal(old_data[i]['change-1']) + Decimal(0.3333)*Decimal(old_data[i]['change-2']) #- Decimal(0.1)*Decimal(ticker_item['percentChange'].encode("utf-8"))
                else:
                   avg_change = Decimal(0.0001) #- Decimal(0.1)*Decimal(ticker_item['percentChange'].encode("utf-8"))
                #if avg_change > 0.00001:
                   #print(timestamp() + " Currency with match is " + ticker.keys()[i] + " with avg change of " + str(avg_change))   
				#   avg_change = 0.00001
                seedchange = Decimal(0)
                if ticker.keys()[i] == seed_data[0]['name']:# and 
                  #print(timestamp() + " Score for " + seed_data[0]['name'] + " is " + str(avg_change))   
                  if Decimal(seed_data[0]['last_value'].encode("utf-8")) > Decimal(0):
                     seedchange = Decimal(ticker_item['last'].encode("utf-8"))/Decimal(seed_data[0]['last_value'].encode("utf-8"))
                  else:
                     seedchange = Decimal(1)                  
                  seedvalue = Decimal(seed_data[0]['value'].encode("utf-8")) * seedchange
                  if seedvalue > Decimal(seed_data[0]['max'].encode("utf-8")):
                     max_prev_seed_value = seedvalue
                  else:
                     max_prev_seed_value = Decimal(seed_data[0]['max'].encode("utf-8"))
                  print(timestamp() + " Present currency Pair is " + seed_data[0]['name'] + " with growth of " + str(seedchange) + ". New seed value is " + str(seedvalue) + " with match index of " + str(match_index) + " and avg_change of " + str(avg_change)) 
                  with open('seedfile.txt', 'w') as seedfilez:
                       json.dump([{"name":seed_data[0]['name'],"max":str(max_prev_seed_value),"value":str(seedvalue),"avg_change":str(avg_change),"match":str(match_index),"last_value":ticker_item['last']}], seedfilez)                   
#                j = 0
                
                if match_index > Decimal(0) and (match_index > Decimal(max_change[0,3]) or ((match_index) == Decimal(max_change[0,3]) and (avg_change) > Decimal(max_change[0,1]))):
                   max_change[0,1] = avg_change
                   max_change[0,2] = change
                   max_change[0,3] = match_index
                   max_change[0,0] = i
                   max_change[0,4] = Decimal(ticker_item['last'].encode("utf-8"))
                   #print("Max avg_change is " + str(max_change[0,1]) + " of currency " + str(ticker.keys()[i]) + " with match index of " + str(max_change[0,3]))
				
				#for rows in max_change:
#                  if match_index > Decimal(0):
#				     if match_index >= max_change[j,3]:
#					    if j > 0 and 
#					 
#				  and j == 0 and match_index >= rows[3] and avg_change >= rows[1]) or (match_index > Decimal(0) and match_index < max_change[j-1,3] and avg_change < max_change[j-1,1] and match_index >= max_change[j,3] and avg_change >= max_change[j-1,1]):    #Decimal(match_index > rows[3] 
 #                   if (avg_change > 0.0001 and j == 0 and avg_change > rows[1]) or (avg_change > 0.0001 and avg_change < max_change[j-1,1] and avg_change > max_change[j,1]):
  #                     #print("change is " + str(change) + " for currenct pair " + ticker.keys()[i])
   #                    max_change[j+1:4,:] = max_change[j:3,:]                 
    #                   max_change[j,1] = avg_change
     #                  max_change[j,2] = change
      #                 max_change[j,3] = max_index
		#			   max_change[j,0] = i
         #              break
          #        j+=1
                temp_row={"name":ticker.keys()[i],"last_price":ticker_item['baseVolume'],"last_price-1":old_data[i]['last_price'],"change":str(change),"change-1":old_data[i]['change'],"change-2":old_data[i]['change-1'],"change-3":old_data[i]['change-2']}
                data.append(temp_row)
                i+=1
    else:
       for ticker_item in ticker.values():
           temp_row={"name":ticker.keys()[i],"last_price":ticker_item['baseVolume'],"last_price-1":str(0),"change":str(0),"change-1":str(0),"change-2":str(0),"change-3":str(0)}
           data.append(temp_row)
           i+=1
    
    #max_change[max_change[:,3].argsort()]
    #i=1
    #for rows in max_change:
    if ticker.keys()[max_change[0,0].astype(numpy.int64)][:3] == 'BTC' and Decimal(max_change[0,3]) > Decimal(0):
       with open('available_pair.txt', 'w') as pairfile:
            json.dump([{"name":ticker.keys()[max_change[0,0].astype(numpy.int64)],"avg_change":str(max_change[0,1]),"match":str(max_change[0,3]),"last_value":str(max_change[0,4])}], pairfile)
    else:
       with open('available_pair.txt', 'w') as pairfile:
            json.dump([{"name":"","avg_change":"","match":"","last_value":""}], pairfile)
       #target.write(ticker.keys()[max_change[0,0].astype(numpy.int64)] + " " + str(100*max_change[0,1]))
            #print(ticker.keys()[max_change[0,0].astype(numpy.int64)] + " with growth of " + str(100*max_change[0,1]) + "% \n")
       #target.close()
	   #i+=1
    with open ('price_tickr.txt', 'w') as outfile:
        json.dump(data, outfile)#, separators=('}}'))
        #print ("price " + ticker_item['baseVolume'] + " pair " + ticker_item['lowestAsk'])		 

def livetrader():
    #global seed
    seed_data=[]
    last_data=[]
    option=[]
    with open('seedfile.txt', 'r') as seedfile:
         seed_data = json.load(seedfile)
         seedamount=Decimal(seed_data[0]['value'].encode("utf-8"))
         seedpair=seed_data[0]['name']
         seedscore=Decimal(seed_data[0]['avg_change'].encode("utf-8"))
         max_prev_seed_value=Decimal(seed_data[0]['max'].encode("utf-8"))
         seedmatchindex=Decimal(seed_data[0]['match'].encode("utf-8"))
         last_curr_val=Decimal(seed_data[0]['last_value'].encode("utf-8"))
		
    with open('available_pair.txt', 'r') as availpair:
         option = json.load(availpair)
         if option[0]['avg_change'] != '':
            availgrowth=Decimal(option[0]['avg_change'].encode("utf-8"))
            availpair=option[0]['name']
            availpairmatchindx = Decimal(option[0]['match'].encode("utf-8"))
            avail_last_value = Decimal(option[0]['last_value'].encode("utf-8"))
         else:
            availgrowth=Decimal(0)
            availpair=''		  
         if availpair != '':
            print(timestamp() + " Available Currency Pair is " + availpair + " with avg_growth of " + str(availgrowth) + " and match index of " + str(availpairmatchindx)) 

    #with open('price_tickr.txt', 'r') as infile:
    #     last_data = json.load(infile)
    #     for items in last_data:
    #       if items['name'] == str(seedpair):
            # seedchange = Decimal(items['change'].encode("utf-8"))
 		 #seedchange=last_data.keys()[seedpair]['change']
		 #last_data[seedpair]['change']
    
    #seedamount *= (1+seedchange)    
    #growth_factor = seedamount/max_prev_seed_value
    #if growth_factor > Decimal(1):
    #   max_prev_seed_value = seedamount
    #   print(timestamp() + " Max Seed Value increased to " + str(max_prev_seed_value))   
	   
    if availpair != '' and seedpair != availpair and availpairmatchindx > Decimal(0):
       if (availpairmatchindx > Decimal(1) and availgrowth > Decimal(120)*seedscore) :#availpairmatchindx > seedmatchindex + 1 or # and Decimal(10)*seedscore < availgrowth): #(seedchange > 0.00001 and availgrowth > (Decimal(1.1))*seedchange) or
          print(timestamp() + " traded to " + availpair + " Previous avg_change was " + str(seedscore) + " and matchindex was " + str(seedmatchindex))   
          seedamount *= Decimal(0.991)#0.996
          seedpair = availpair
          last_curr_val = avail_last_value
          #max_prev_seed_value = seedamount
          #print(timestamp() + " Max Seed Value reduced to " + str(max_prev_seed_value))   
       #elif (seedscore <= -0.003 and availgrowth > Decimal(0.05)):  
       #   print(timestamp() + " traded to " + availpair + " Previous score was " + str(seedscore) + " new score is " + str(availgrowth))   
       #   seedamount *= Decimal(0.991)
       #   seedpair = availpair
    #elif seedpair != 'USDT_BTC':
    #   if (growth_factor > 1.35 or growth_factor < 0.8): 
    #      print(timestamp() + " Default traded to USDT_BTC. Previous rate was " + str(seedchange))   
    #      seedamount *= Decimal(0.991)#0.996
    #      seedpair = 'USDT_BTC'
          #max_prev_seed_value = seedamount
    print(timestamp() + " seedamount is " + str(seedamount))   
    print("<<<<<< *********** >>>>>>>>>> ")   
    with open('seedfile.txt', 'w') as newseedfile:
         json.dump([{"name":seedpair,"value":str(seedamount),"max":str(max_prev_seed_value),"avg_change":str(seedscore),"match":str(seedmatchindex),"last_value":str(last_curr_val)}], newseedfile)

def refreshTotalLended():
	global totalLended, rateLended
	cryptoLended = bot.returnActiveLoans()	

	totalLended = {}
	rateLended = {}
	cryptoLendedSum = Decimal(0)
	cryptoLendedRate = Decimal(0)

	for item in cryptoLended["provided"]:
		itemStr = item["amount"].encode("utf-8")
		itemFloat = Decimal(itemStr)
		itemRateStr = item["rate"].encode("utf-8")
		itemRateFloat = Decimal(itemRateStr)
		if item["currency"] in totalLended:
			cryptoLendedSum = totalLended[item["currency"]] + itemFloat
			cryptoLendedRate = rateLended[item["currency"]] + (itemRateFloat * itemFloat)
			totalLended[item["currency"]] = cryptoLendedSum
			rateLended[item["currency"]] = cryptoLendedRate
		else:
			cryptoLendedSum = itemFloat
			cryptoLendedRate = itemRateFloat * itemFloat
			totalLended[item["currency"]] = cryptoLendedSum
			rateLended[item["currency"]] = cryptoLendedRate

def stringifyTotalLended():
	result = 'Lended: '
	for key in sorted(totalLended):
		result += '[%.3f %s @ %.4f%%] ' % (Decimal(totalLended[key]), key, Decimal(rateLended[key]*100/totalLended[key]))
	return result

def createLoanOffer(cur,amt,rate):
	days = '2'
	#if (minDailyRate - 0.000001) < rate and Decimal(amt) > 0.001:
	if float(amt) > 0.001:
		rate = float(rate) - 0.000001 #lend offer just bellow the competing one
		amt = "%.8f" % Decimal(amt)
		if rate > sixtyDayThreshold:
			days = '60'
		if sixtyDayThreshold == 0:
			days = '2'
		if dryRun == False:
			msg = bot.createLoanOffer(cur,amt,days,0,rate)
			log.offer(amt, cur, rate, days, msg)

def cancelAndLoanAll():
	loanOffers = bot.returnOpenLoanOffers('BTC') #some bug with api wrapper? no idea why I have to provide a currency, and then receive every other
	if type(loanOffers) is list: #silly api wrapper, empty dict returns a list, which brakes the code later.
		loanOffers = {}
	if loanOffers.get('error'):
		print loanOffers.get('error')
		print 'You might want to edit config file (default.cfg) and put correct apisecret and key values'
		exit(1)

	onOrderBalances = {}
	for cur in loanOffers:
		for offer in loanOffers[cur]:
			onOrderBalances[cur] = onOrderBalances.get(cur, 0) + Decimal(offer['amount'])
			if dryRun == False:
				msg = bot.cancelLoanOffer(cur,offer['id'])
				log.cancelOrders(cur, msg)

	lendingBalances = bot.returnAvailableAccountBalances("lending")['lending']
	if dryRun == True: #just fake some numbers, if dryrun (testing)
		if type(lendingBalances) is list: #silly api wrapper, empty dict returns a list, which brakes the code later.
			lendingBalances = {}
		lendingBalances.update(onOrderBalances)

	for activeCur in lendingBalances:

		activeBal = lendingBalances[activeCur]

		#min daily rate can be changed per currency
		curMinDailyRate = minDailyRate
		if activeCur in coincfg:
			if coincfg[activeCur]['maxactive'] == 0:
				log.log('maxactive amount for ' + activeCur + ' set to 0, won\'t lend.')
				continue
			curMinDailyRate = coincfg[activeCur]['minrate']
			log.log('Using custom mindailyrate ' + str(coincfg[activeCur]['minrate']*100) + '% for ' + activeCur)

		loans = bot.returnLoanOrders(activeCur)
		s = Decimal(0) #sum
		i = int(0) #offer book iterator
		j = int(0) #spread step count
		lent = Decimal(0)
		step = (gapTop - gapBottom)/spreadLend
		#TODO check for minimum lendable amount, and try to decrease the spread. e.g. at the moment balances lower than 0.001 won't be lent
		#in case of empty lendbook, lend at max
		activePlusLended = Decimal(activeBal)
		if activeCur in totalLended:
			activePlusLended += Decimal(totalLended[activeCur])
		if len(loans['offers']) == 0:
			createLoanOffer(activeCur,Decimal(activeBal)-lent,maxDailyRate)
		for offer in loans['offers']:
			s = s + Decimal(offer['amount'])
			s2 = s
			while True:
				if s2 > activePlusLended*(gapBottom/100+(step/100*j)) and Decimal(offer['rate']) > curMinDailyRate:
					j += 1
					s2 = s2 + Decimal(activeBal)/spreadLend
				else:
					createLoanOffer(activeCur,s2-s,offer['rate'])
					lent = lent + (s2-s).quantize(SATOSHI)
					break
				if j == spreadLend:
					createLoanOffer(activeCur,Decimal(activeBal)-lent,offer['rate'])
					break
			if j == spreadLend:
				break
			i += 1
			if i == len(loans['offers']): #end of the offers lend at max
				createLoanOffer(activeCur,Decimal(activeBal)-lent,maxDailyRate)

def setAutoRenew(auto):
	i = int(0) #counter
	try:
		action = 'Clearing'
		if(auto == 1):
			action = 'Setting'
		log.log(action + ' AutoRenew...(Please Wait)')
		cryptoLended = bot.returnActiveLoans()
		loansCount = len(cryptoLended["provided"])
		for item in cryptoLended["provided"]:
			if int(item["autoRenew"]) != auto:
				log.refreshStatus('Processing AutoRenew - ' + str(i) + ' of ' + str(loansCount) + ' loans')
				bot.toggleAutoRenew(int(item["id"]))
				i += 1
	except KeyboardInterrupt:
		log.log('Toggled AutoRenew for ' +  str(i) + ' loans')
		raise SystemExit
	log.log('Toggled AutoRenew for ' +  str(i) + ' loans')

log.log('Welcome to Poloniex Lending Bot')

while True:
    try:
        tradingbot()
        livetrader()
        #refreshTotalLended()
        #log.refreshStatus(stringifyTotalLended())
        #cancelAndLoanAll()
        time.sleep(sleepTime)
    except Exception as e:
        log.log("ERROR: " + str(e))
        time.sleep(sleepTime)
        pass
    except KeyboardInterrupt:
#		if autorenew == 1:
#			setAutoRenew(1);
        log.log('bye')
        exit(0)
