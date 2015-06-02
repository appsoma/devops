import sys
import os
import shutil
import process
import sqlite3
import urllib2

def createDB(db_path):
	if not db_path: db_path = database_path
	with db as sqlite3.connect(db_path):
		values = { "url": "varchar(255)", "app": "varchar(255)" }
		cols = []
		for k in values:
			cols.append(" ".join([k,values[k]]));
	
		db.execute("CREATE TABLE IF NOT EXISTS "+table+" ("+cols.join(",")+")");
		db.commit()

def createCronJob():
	os.makedirs(script_dir)
	createDB(database_path)
	os.mkdir(cronjob_dir)
	with f as open(cronjob,"w"):
		f.write(cronContent())
	shutil.copyfile(script,script_path)
	os.chmod(script_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

def updateConfig(masters):
	config = configHeader() + "\n".join(configApps(masters))
	with f as open("/etc/haproxy/"+conf_file,"r"):
		content = f.read()

	if content == config: return
	with f as open("/etc/haproxy/"+conf_file,"w"):
		f.write(config)
	
	print subprocess.Popen("/bin/bash -c 'haproxy -f /etc/haproxy/haproxy.cfg -p /var/run/haproxy-private.pid -sf $(</var/run/haproxy-private.pid)', shell=True, stdout=subprocess.PIPE")

def configApps(masters):
	masters = masters.split("\n");

	with db as sqlite3.connect(database_path):
		apps = {}
		for row in db.execute("SELECT * FROM "+table):
			apps[row["app"]] = row

	content = []
	for master in masters:
		response = urllib2.urlopen("http://"+master+"/v2/tasks")
		lines = response.read().split("\n")
		for line in lines:
			appsWithUrl = []
			if line.strip() == "": next
			parts = line.split("\t");
			app_name = parts[0]
			service_port = parts[1]
			servers = parts[2:]

			if apps[app_name]:
				appsWithUrl.append({ url: apps[app_name].url, app_name: app_name, service_port: service_port, servers: servers})
				next
							
			server_config = listenAppFromPort(app_name,service_port,servers)
			content = content + server_config
	
		if appsWithUrl.length: content = content + listenAppFromUrl(appsWithUrl)
	return content

def listenAppFromUrl(apps):
	frontends = [ "frontend http" ]
	ifs = []
	backends = []

	for app in apps:
		app_name = app["app_name"]
		frontend = ""
		if(app.url[0] == "/"): frontend = "acl "+app_name+" path_end -i "+app["url"]
		else: frontend = "acl "+app_name+" hdr_beg(host) -i "+app["url"]

		frontends.append(frontend)
		ifs.append("use_backend srvs_"+app_name+"    if "+app_name)
		backend = [
			"backend srvs_"+app_name,
			"   mode tcp",
			"   option tcplog",
			"   balance leastconn",
		]
		for s in range(len(app["servers"])):
			server = app.servers[s]
			if(server.strip() == "") next
			backend.push("   server host"+s+" "+server)
		backends = backends + backend
	
	apps = frontends + ifs
	apps = apps + backends
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
		if server.strip() == "": next
		server_config.append("  server "+app_name+"-"+i+" "+server+" check")

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
	args = sys.argv[1:]

	if method in methods:
		globals()[](*args)
	else:
		print "Wrong methods"
