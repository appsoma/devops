#!/usr/bin/python
import sys
import stat
import os
import shutil
import subprocess
import sqlite3
import urllib2
import json

script = sys.argv[0].split("/")[-1]
name = ".".join(script.split(".")[:-1])
table = "urls"
database = name
script_dir = "/usr/local/bin/"+name+"-dir/"
database_path = script_dir+name
extra_services_conf_file = "/etc/"+name+"/services.json"
cronjob_conf_file = "/etc/"+name+"/marathons"
cronjob_dir = "/etc/cron.d/"
cronjob = cronjob_dir+name
script_path = script_dir+script
conf_file = "haproxy.cfg"

def createDB(db_path=False):
	if not db_path: db_path = database_path
	print "test",db_path
	with sqlite3.connect(db_path) as db:
		values = { "url": "varchar(255)", "app": "varchar(255)" }
		cols = []
		for k in values:
			cols.append(" ".join([k,values[k]]));
	
		db.execute("CREATE TABLE IF NOT EXISTS "+table+" ("+",".join(cols)+")");
		db.commit()

def addUrl(app,url):
	with sqlite3.connect(database_path) as db:
		db.execute("INSERT INTO "+table+"(url,app) VALUES('"+app+"','"+url+"')");
		db.commit()

def createCronJob():
	try:
		os.makedirs(script_dir)
	except:
		pass
	createDB(database_path)
	try:
		os.mkdir(cronjob_dir)
	except: 
		pass
	with open(cronjob,"w") as f:
		f.write(cronContent())
	shutil.copyfile(script,script_path)
	os.chmod(script_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

def updateConfig(masters):
	config = "\n".join(configHeader() + configApps(masters))
	with open("/etc/haproxy/"+conf_file,"r") as f:
		content = f.read()

	if content == config: return
	with open("/etc/haproxy/"+conf_file,"w") as f:
		f.write(config)

	pids = False
	try:
		with open("/var/run/haproxy-private.pid","r") as f:
			pids = f.read().replace("\n"," ")
	# ACB: File may not exist
	except: pass

	pids_string = (" -sf "+pids) if pids else ""

	print subprocess.Popen("/bin/bash -c 'haproxy -f /etc/haproxy/haproxy.cfg -p /var/run/haproxy-private.pid"+pids_string+"'", shell=True, stdout=subprocess.PIPE)

def configApps(masters):
	masters = masters.split("\n");

	with sqlite3.connect(database_path) as db:
		apps = {}
		for row in db.execute("SELECT * FROM "+table):
			apps[row[0]] = {"app":row[0],"url":row[1]}

	content = []
	appsWithUrl = []
	for master in masters:
		req = urllib2.Request("http://"+master+"/v2/tasks", None, { "Accept": "text/plain" })
		response = urllib2.urlopen(req)
		lines = response.read().split("\n")
		for line in lines:
			if line.strip() == "": continue
			parts = line.split("\t");
			app_name = parts[0]
			service_port = parts[1]
			servers = parts[2:]

			print app_name
			if app_name in apps:
				appsWithUrl.append({ "url": apps[app_name]["url"], "app_name": app_name, "service_port": service_port, "servers": servers})
			else:							
				server_config = listenAppFromPort(app_name,service_port,servers)
				content += server_config

	try:
		with open(extra_services_conf_file,"r") as f:
			apps = json.loads(f.read())
			appsWithUrl += apps
	#ACB: May not exist
	except: pass
	
	if len(appsWithUrl) > 0: content += listenAppFromUrl(appsWithUrl)
	return content

def listenAppFromUrl(apps):
	frontends = [ 
		"",
		"frontend http-in",
		"   bind 0.0.0.0:80",
		"   mode http",
		"   option tcplog"
	]
	ifs = []
	backends = []

	for app in apps:
		app_name = app["app_name"]
		frontend = ""
		if(app["url"][0] == "/"): frontend = "   acl "+app_name+" path_end -i "+app["url"]
		else: frontend = "   acl "+app_name+" hdr(host) -i "+app["url"]

		frontends.append(frontend)
		ifs.append("use_backend srvs_"+app_name+"    if "+app_name)
		backend = [
			"",
			"backend srvs_"+app_name,
			"   mode http",
			"   option httpclose",
			"   option forwardfor",
			"   balance leastconn"
		]
		for s in range(len(app["servers"])):
			server = app["servers"][s]
			if server.strip() == "": continue
			backend.append("   server host"+str(s)+" "+server)
		backends = backends + backend
	
	apps = frontends + ifs
	apps = apps + backends
	print apps
	return apps

def listenAppFromPort(app_name,service_port,servers):
	server_config = [
		"listen "+app_name+"-"+service_port,
		"  bind 0.0.0.0:"+service_port,
		"  mode tcp",
		"  option tcplog",
		"  balance leastconn"
	]

	for i in range(len(servers)):
		server = servers[i]
		if server.strip() == "": continue
		server_config.append("  server "+app_name+"-"+str(i)+" "+server+" check")

	return server_config

def cronContent():
	return "* * * * * root "+script_path+" updateConfig $(cat "+cronjob_conf_file+")"

def configHeader():
	header = [
		"global",
		"  daemon",
		"  nbproc 2",
		"  pidfile /var/run/haproxy-private.pid",
		"  log 127.0.0.1 local0",
		"  log 127.0.0.1 local1 notice",
		"  maxconn 4096",
		"",
		"defaults",
		"  log            global",
		"  retries             3",
		"  maxconn          2000",
		"  timeout connect  5000",
		"  timeout client  50000",
		"  timeout server  50000",
		"  option httplog",
		"  option dontlognull",
		"  option forwardfor",
		"  option http-server-close",
		"",
		"listen stats",
		"  bind 127.0.0.1:9090",
		"  balance",
		"  mode http",
		"  stats enable",
		"  stats auth admin:admin"
	]
	return header

if __name__ == "__main__":
	method = sys.argv[1]
	args = sys.argv[2:]

	if method in globals():
		globals()[method](*args)
	else:
		print "Wrong methods"
