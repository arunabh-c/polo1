#!/usr/bin/python
import urllib2
import csv
import math
import re
import time
import os
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from datetime import datetime, timedelta
from Robinhood import Robinhood

my_trader = Robinhood();
my_trader.login(username="", password="")

start_seed = 1000.0
min_days_to_hold_stk = 120
max_stx_to_hold = 5
stk_grwth_purchase_threshold = [0.09,1.0]#in %
total_5minute_intervals_to_check_avg_growth = 10 

with open('select_order.csv', 'rb') as f:
	    reader = csv.reader(f)
	    select_order = list(reader)

def get_stock_name(page_source):
        start = page_source.index("quote.ashx?t=") + len("quote.ashx?t=")
        end = page_source.index("&ty=c&p=d&b=1", start )
        return page_source[start:end]

def check_buy_opportunity(stk):
	global stk_grwth_purchase_threshold, total_5minute_intervals_to_check_avg_growth
	todays_perf = my_trader.get_historical_quotes(stk,'5minute','day','regular')
	weeks_perf = my_trader.get_historical_quotes(stk,'5minute','week','regular')
	avg_growth = 0.0
	todays_perf_size = len(todays_perf['results'][0]['historicals'])
	weeks_perf_size = len(weeks_perf['results'][0]['historicals'])
	'''print todays_perf['results'][0]['historicals'][todays_perf_size-1]
	print weeks_perf['results'][0]['historicals'][weeks_perf_size-todays_perf_size-1]
	print weeks_perf['results'][0]['historicals'][weeks_perf_size-todays_perf_size-79]
	print weeks_perf['results'][0]['historicals'][weeks_perf_size-todays_perf_size-157]'''
	close_price_right_now = float(todays_perf['results'][0]['historicals'][todays_perf_size-1]['close_price'])
	yesterday_close_price = float(weeks_perf['results'][0]['historicals'][weeks_perf_size-todays_perf_size-1]['close_price'])
	day_before_yesterday_close_price = float(weeks_perf['results'][0]['historicals'][weeks_perf_size-todays_perf_size-79]['close_price'])
	day_before_day_before_yesterday_close_price = float(weeks_perf['results'][0]['historicals'][weeks_perf_size-todays_perf_size-157]['close_price'])
	perf_today = 100.0 * (close_price_right_now - yesterday_close_price)/yesterday_close_price
	print (str(datetime.now()) + " Performance today for " + stk + ": " + str(perf_today))
	perf_yesterday = 100.0 * (yesterday_close_price - day_before_yesterday_close_price)/day_before_yesterday_close_price
	print (str(datetime.now()) + " Performance yesterday for " + stk + ": " + str(perf_yesterday))
	perf_day_before_yesterday = 100.0 * (day_before_yesterday_close_price - day_before_day_before_yesterday_close_price)/day_before_day_before_yesterday_close_price
	print (str(datetime.now()) + " Performance day before yesterday for " + stk + ": " + str(perf_day_before_yesterday))
	
	if todays_perf_size >= 11:#Avg. % growth of last 50 minutes
		for i in range(0,total_5minute_intervals_to_check_avg_growth):
			avg_growth = avg_growth + 10.0*(float(todays_perf['results'][0]['historicals'][todays_perf_size-1-i]['close_price']) - float(todays_perf['results'][0]['historicals'][todays_perf_size-2-i]['close_price']))/(float(todays_perf['results'][0]['historicals'][todays_perf_size-2-i]['close_price']))
		print (str(datetime.now()) + " Last " + str(5*total_5minute_intervals_to_check_avg_growth) + " minutes growth for " + stk + ": " + str(avg_growth))

	if  (perf_today <= stk_grwth_purchase_threshold[0] or perf_yesterday <= stk_grwth_purchase_threshold[0]) and (perf_yesterday <= stk_grwth_purchase_threshold[0] or perf_day_before_yesterday <= stk_grwth_purchase_threshold[0]) and (avg_growth >= stk_grwth_purchase_threshold[0] and avg_growth <= stk_grwth_purchase_threshold[1]):
		buy_permit = True
	else:
		buy_permit = False
	return buy_permit

def replace_parameter(old_param, new_param, url):
	init_url = url
	repl = re.subn(old_param, new_param, url)
	url = repl[0]
	replace_count = repl[1]
	return url, init_url, replace_count

def purchase_logger(stock, quantity, stock_price, free_cash, stk_to_sell_idx):
	
	global max_stx_to_hold
	file_write_array = [str(datetime.now().strftime("%Y-%m-%d %H:%M")),stock, str(quantity), str(stock_price), str(free_cash)]
	trade_history = (os.stat('daily_last_state.txt').st_size != 0)

	if trade_history == False:
		f = open('daily_last_state.txt', 'w')
		for j in range(0,len(file_write_array)):
			if j == 4:
				f.write(file_write_array[j])
			else:
				f.write(file_write_array[j] + '\n')
	else:
		row_counter = 0
		file_lines = ["","","","",""]
		with open('daily_last_state.txt', 'r') as f:
			for line in f:
				if row_counter == 4:
					file_lines[row_counter] = file_write_array[row_counter]
				else:
					if stk_to_sell_idx != -1:
						if stk_to_sell_idx == max_stx_to_hold-1:
							file_lines[row_counter] = line.replace(',' + (line.rstrip('\n')).split(",")[stk_to_sell_idx],'')
						else:
							file_lines[row_counter] = line.replace((line.rstrip('\n')).split(",")[stk_to_sell_idx] + ',','')
					else:	
						file_lines[row_counter] = line
					file_lines[row_counter] = (file_lines[row_counter].rstrip('\n') + ',' + file_write_array[row_counter] + '\n')
				row_counter = row_counter + 1

		with open('daily_last_state.txt', 'w') as f:
			f.writelines(file_lines) 
	f.close()

def send_email(message):
	fromaddr = ""
	toaddr = ""
	msg = MIMEMultipart()
	msg['From'] = fromaddr
	msg['To'] = toaddr
	msg['Subject'] = "Stock Activity"
 
	msg.attach(MIMEText(message, 'plain'))
 
	server = smtplib.SMTP('smtp.gmail.com', 587)
	server.starttls()
	server.login(fromaddr, "")
	text = msg.as_string()
	server.sendmail(fromaddr, toaddr, text)
	server.quit()
	
def check_robinhood_stock_availability(stock):
	try:
		if float(my_trader.last_trade_price(stock)) > 0.0:
			return False
	except:
		return True

def last_state_reader():
		global start_seed, my_trader
		holdings_array = [[], [], [], []]
		last_purchase_time = []
		last_stock = []
		last_stock_quantity = []
		last_stock_purchase_price = []
		f = open('daily_last_state.txt', 'r')		
		try:
			row_counter = 0
			for line in f:
				if row_counter < 4:
					holdings_array[row_counter] = (line.rstrip('\n')).split(",")
				if row_counter == 4:
					free_cash = float(line.rstrip('\n'))
				row_counter = row_counter + 1
		finally:
		    f.close()		    	
		if len(holdings_array[0]) > 0:
			last_stock = holdings_array[1]
			new_balance = free_cash
			for j in range(0,len(holdings_array[0])):
				last_purchase_time.append(datetime.strptime(holdings_array[0][j], "%Y-%m-%d %H:%M"))   
				last_stock_quantity.append(float(holdings_array[2][j]))
				last_stock_purchase_price.append(float(holdings_array[3][j]))
				last_stock_present_price = float(my_trader.last_trade_price(last_stock[j]))
				new_balance = new_balance + last_stock_quantity[j] * last_stock_present_price
				gains_since_stk_purchase = 100.0*(last_stock_present_price - last_stock_purchase_price[j])/last_stock_purchase_price[j]
				days_left_to_sale = min_days_to_hold_stk - (datetime.now() - last_purchase_time[j]).days
				print ("Stock holding: " + last_stock[j] + " on " + str(last_purchase_time[j]) + ", Gain since last purchase: " + str(gains_since_stk_purchase) + "%, Days before sale: " + str(days_left_to_sale))

			gains_since_beginning = 100.0*(new_balance - start_seed)/start_seed
			print ("Net Gain since beginning: " + str(gains_since_beginning) + "%")
			print ("Latest Balance: " + str(new_balance))
		else:
			new_balance = start_seed
			free_cash = start_seed

		return last_purchase_time, last_stock, last_stock_quantity, last_stock_purchase_price, free_cash, new_balance

def time_to_sleep():
	day = datetime.now().isoweekday()
	hour =  datetime.now().hour
	minute = datetime.now().minute
	second = datetime.now().second
	tts = 300
	if (day in range(1,6)) and (hour in range(8,17)):#mon-fri 8am-6pm, run every 5 minutes
		tts = 300
	elif (day in range(1,6)) and (hour > 17):#mon-fri 6pm-12am, sleep till 8 am
		tts = (32 - hour)*3600 - minute*60 - second
	elif (day in range(1,6)) and (hour < 8):#mon-fri pre-8am, sleep till 8 am
		tts = (8-hour)*3600 - minute*60 - second
	elif (day > 5):#weekend, sleep till monday 8am
		tts = (7-day)*24*3600 + (32-hour)*3600 - minute*60 - second
	if tts > 300:
	    d = datetime(1,1,1) + timedelta(seconds=tts)
	    print("Sleeping for ")
	    print("%d:%d:%d:%d" % (d.day-1, d.hour, d.minute, d.second))
	    d = datetime.now() + timedelta(seconds=tts)
	    print("Wake up at " + d.strftime("%A"))
	    print("%d:%d:%d" % (d.hour, d.minute, d.second))
	return tts

def purchase_accounting(last_purchase_time, last_stock, last_stock_quantity, last_stock_purchase_price, free_cash, final_stock):
	global min_days_to_hold_stk, max_stx_to_hold, my_trader
	
	final_stock_price = float(my_trader.last_trade_price(final_stock))
	oldest_stk_idx = -1
	if len(last_stock) < max_stx_to_hold:
		available_cash = free_cash/(max_stx_to_hold - len(last_stock))
	else:
		oldest_stk_idx = last_purchase_time.index(min(last_purchase_time))
		sale_price = float(my_trader.last_trade_price(last_stock[oldest_stk_idx]))
		available_cash = free_cash + last_stock_quantity[oldest_stk_idx] * sale_price
		print (str(datetime.now()) + " Stock sold: " + last_stock[oldest_stk_idx] + ", Profit % made: " + str(100.0*(sale_price-last_stock_purchase_price[oldest_stk_idx])/last_stock_purchase_price[oldest_stk_idx]))
		with open('daily_activity_log.txt', 'a`') as f:
			f.writelines(str(datetime.now()) + " Stock sold: " + last_stock[oldest_stk_idx] + ", Profit % made: " + str(100.0*(sale_price-last_stock_purchase_price[oldest_stk_idx])/last_stock_purchase_price[oldest_stk_idx]) + '\n')
		send_email(str(datetime.now()) + " Stock sold: " + last_stock[oldest_stk_idx] + ", Profit % made: " + str(100.0*(sale_price-last_stock_purchase_price[oldest_stk_idx])/last_stock_purchase_price[oldest_stk_idx]))
	total_stocks = math.floor(available_cash/final_stock_price)
	final_purchase_amount = final_stock_price * total_stocks
	if len(last_stock) < max_stx_to_hold:
		free_cash = free_cash - final_purchase_amount
	else:
		free_cash = available_cash - final_purchase_amount

	purchase_logger(final_stock, total_stocks, final_stock_price, free_cash, oldest_stk_idx)
	print (str(datetime.now()) + " Stock purchased: " + final_stock + ", Total stocks: " + str(total_stocks) + ", Final purchase amount: " + str(final_purchase_amount))
	with open('daily_activity_log.txt', 'a`') as f:
			f.writelines(str(datetime.now()) + " Stock purchased: " + final_stock + ", Total stocks: " + str(total_stocks) + ", Final purchase amount: " + str(final_purchase_amount) + '\n')
	send_email(str(datetime.now()) + " Stock purchased: " + final_stock + ", Total stocks: " + str(total_stocks) + ", Final purchase amount: " + str(final_purchase_amount))

	print (str(datetime.now()) + " Free cash left: " + str(free_cash))

def check_stock_eligibility(last_purchase_time,last_stock,final_stock):
	global min_days_to_hold_stk, max_stx_to_hold
	buy_flag = False
	if final_stock not in last_stock:
		if len(last_stock) < max_stx_to_hold:
			buy_flag = True
		elif len(last_stock) == max_stx_to_hold: 
			latest_purchase_date = datetime.now() - timedelta(days=min_days_to_hold_stk)
			for i in range(0,len(last_purchase_time)):
				if last_purchase_time[i] < latest_purchase_date:
						buy_flag = True
						break
	return buy_flag

def result_check(url,last_stock):
	global my_trader
	response = urllib2.urlopen(url)
	page_source = response.read()
        
	stock = []
	prefix ="quote.ashx?t="
       
	for i in range (0,int(page_source.count(prefix)/11)):
		stk = get_stock_name(page_source)
		for i in range(0,11):
			page_source = page_source.replace(str("quote.ashx?t=" + stk + "&ty=c&p=d&b=1"),"")#Delete first stock from page source string to arrive at next stock

		if stk not in last_stock:
			stock.append(stk)

	return stock

def optimize(last_stock,last_purchase_time):
	global max_stx_to_hold,min_days_to_hold_stk
	allowed_stk_cnt = 0
	url = "http://finviz.com/screener.ashx?v=111&f=an_recom_holdbetter,fa_debteq_u1,fa_epsqoq_high,fa_netmargin_o5,fa_pe_u10,fa_quickratio_o1,fa_roe_pos,ta_perf_1wdown,ta_perf2_4wdown,ta_rsi_os40,ta_sma20_pb,ta_sma200_pb,ta_sma50_pb&ft=4"
	prev_url = url
	repl_count = 0	
	tmp_stock = []
	latest_purchase_date = datetime.now() - timedelta(days=min_days_to_hold_stk)

	for i in range(0,len(last_purchase_time)):
		if last_purchase_time[i] < latest_purchase_date:
			allowed_stk_cnt = allowed_stk_cnt + 1
	if len(last_stock) < max_stx_to_hold:
		allowed_stk_cnt = allowed_stk_cnt + max_stx_to_hold - len(last_stock)
	
	tmp_stock = result_check(url,last_stock)
	while len(tmp_stock) > allowed_stk_cnt and select_order_index < len(select_order):
		filter_success_flag = False
		if len(tmp_stock) > allowed_stk_cnt:
			url, prev_url, repl_count = replace_parameter(select_order[select_order_index][0],select_order[select_order_index][1], url)
			tmp_stock = result_check(url,last_stock)
			filter_success_flag = True
		if len(tmp_stock) < 1 or (len(tmp_stock) == 1 and check_robinhood_stock_availability(tmp_stock[0])):
			url = prev_url
			tmp_stock = result_check(url,last_stock)
			filter_success_flag = False
		if filter_success_flag == True and repl_count == 1:
			print ("Filtered on " + select_order[select_order_index][2])
		select_order_index = select_order_index + 1
	return tmp_stock

if __name__ == '__main__':
	print ("Starting Loop..")
	while True:
		if (datetime.now().isoweekday() in range(1,6)) and (datetime.now().hour in range(8,17)):
			last_purchase_time, last_stock, last_stock_quantity, last_stock_purchase_price, free_cash, new_balance = last_state_reader() 

			final_stock = optimize(last_stock,last_purchase_time)

			for i in range(0,len(final_stock)):
				print (str(datetime.now()) + " Most suitable stock: " + final_stock[i])
				final_stock_price = float(my_trader.last_trade_price(final_stock[i]))
				stk_tradeable_on_robinhood = my_trader.instruments(final_stock[i])[0]['tradeable']
				if stk_tradeable_on_robinhood == 'True' and final_stock_price > 0.0 and check_stock_eligibility(last_purchase_time,last_stock,final_stock[i]):
					if check_buy_opportunity(final_stock[i]):
						purchase_accounting(last_purchase_time, last_stock, last_stock_quantity, last_stock_purchase_price, free_cash, final_stock[i])
						last_purchase_time, last_stock, last_stock_quantity, last_stock_purchase_price, free_cash, new_balance = last_state_reader()
		sleep_duration = time_to_sleep()
		time.sleep(sleep_duration)