import sqlite3, re
from datetime import datetime
from threading import Thread
from flask import Flask
from flask import request
from flask import render_template
app = Flask(__name__)

from subprocess import Popen
from subprocess import PIPE
import time
import xprintidle
#https://pypi.python.org/pypi/xprintidle

def secondsToTime(seconds):
	m, s = divmod(seconds, 60)
	h, m = divmod(m, 60)

	return '{:d}:{:02d}:{:02d}'.format(h, m, s)

def get_count(date, con, cur):
		sum={"else": 0, "idle": 0};
		cur.execute('SELECT * FROM track WHERE date =?', (date, ))
		tracks = cur.fetchall()
		for track in tracks:
			track = dict(zip(track.keys(), track))
			if track["program"] == "idle":
				sum["idle"] += track["seconds"]
				continue

			cur.execute('SELECT * FROM rules WHERE els!=1')
			rules = cur.fetchall()
			els = True
			for rule in rules:
				rule = dict(zip(rule.keys(), rule))

				if re.search(rule["rule"], track["program"]):
					try:
						sum[rule["cat"]] += track["seconds"]
					except Exception:
						sum[rule["cat"]] = track["seconds"]
					els=False
					break

			if els:
				sum["else"] += track["seconds"]
			sum["date"] = track["date"]

		cur.execute('SELECT * FROM rules WHERE els=1 LIMIT 0,1')
		results = cur.fetchall()
		for result in results:
			result = dict(zip(result.keys(), result))
			else_value = result["cat"]
			sum[else_value] = sum["else"]
		del sum["else"]
		return sum;

@app.route("/", methods=['GET', 'POST'])
def root():
	con = sqlite3.connect('track.sqlite')
	con.row_factory = sqlite3.Row
	cur = con.cursor()
	date = datetime.now().strftime('%Y-%m-%d')

	if request.args.get("date"):
		date = request.args.get("date")

	if request.form.get("cat"):
		cur.execute("INSERT INTO rules (rule, els, cat) VALUES (?, ?, ?)", (request.form.get("rule"), request.form.get("else"), request.form.get("cat"),))
		con.commit()

	if request.args.get("del"):
		cur.execute("DELETE FROM rules WHERE id=?", (request.args.get("del"),))
		con.commit()

	sum = get_count(date, con, cur);

	sum_table = '<table id="sum"><tr><td><strong>'+date+'</strong></td><td></td></tr>'
	for key in sum.keys():
		if key != "date":
			sum_table += "<tr><td>" + key + "</td><td>" + secondsToTime(sum[key]) + "</td></tr>"
	sum_table += "</table>"

	lista = '<table>'
	cur.execute('SELECT * FROM track WHERE date = ? ORDER BY seconds DESC', (date, ))
	results = cur.fetchall()
	for result in results:
		result = dict(zip(result.keys(), result))
		lista +=  "<tr><td>" + result["program"] + "</td><td>" + str(result["seconds"]) + " seconds</td></tr>"
	lista += '</table>'

	rules = '<table>'
	cur.execute('SELECT * FROM rules ORDER BY els DESC')
	results = cur.fetchall()
	for result in results:
		result = dict(zip(result.keys(), result))

		if result["els"] == 1:
			defaultcat = result["cat"]
		else:
			rules += '<tr><td><a href="?del=' + str(result["id"]) + '">delete</a></td><td>' + result["rule"] + "</td><td>" + result["cat"] + "</td></tr>"
	rules += '</table>'

	cur.execute('SELECT * FROM track GROUP BY date ORDER BY date ASC')
	results = cur.fetchall()
	sums=[]
	for result in results:
		result = dict(zip(result.keys(), result))
		sums.append(get_count(result["date"], con, cur))

	cur.execute('SELECT cat FROM rules GROUP BY cat')
	results = cur.fetchall()
	cats=[]
	for result in results:
		result = dict(zip(result.keys(), result))
		cats.append(result["cat"])
	cats.append("idle")

	return render_template('index.html', defaultcat = defaultcat, sum_table = sum_table, list = lista, rules = rules, sums = sums, cats = cats)

def get_active_window_title():
	root = Popen(['xprop', '-root', '_NET_ACTIVE_WINDOW'], stdout=PIPE)

	for line in root.stdout:
		m = re.search('^_NET_ACTIVE_WINDOW.* ([\w]+)$', line.decode('utf-8'))
		if m != None:
			id_ = m.group(1)
			id_w = Popen(['xprop', '-id', id_, 'WM_NAME'], stdout=PIPE)
			break

	if id_w != None:
		for line in id_w.stdout:
			match = re.match("WM_NAME\(\w+\) = (?P<name>.+)$", line.decode('utf-8'))
			if match != None:
				return match.group("name")

	return "Active window not found"

class Tracker (Thread):
	def __init__(self):
		Thread.__init__(self)
	def run(self):
		con = sqlite3.connect('track.sqlite')
		with con:
			cur = con.cursor()
			while(1):
				try:
					program = get_active_window_title()
					program = re.sub('[^A-Za-z0-9\.]+', ' ', program)

					idle = xprintidle.idle_time()/1000
					if idle>10:
						program="idle"

					date = []
					today = datetime.now().strftime('%Y-%m-%d')
					date.append(today)
					date=str(date[0])

					cur.execute('SELECT * FROM track WHERE date = "'+date+'" and program = "'+program+'"')
					ck = cur.fetchall()
				
					if len(ck) == 0:
						cur.execute('INSERT INTO track (date, program, seconds) VALUES ("'+date+'", "'+program+'", "1")')
					else:
						cur.execute('UPDATE track SET seconds=seconds+1 WHERE date="'+date+'" AND program="'+program+'"')
					con.commit() 

					time.sleep(1)
				except Exception as e:
					print(e)
					pass

thread1 = Tracker()
thread1.start()

app.run(port = 3000)

thread1.join()