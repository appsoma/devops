#!/usr/bin/python
import sys
import stat
import os
import shutil
import subprocess
import urllib
import urllib2
import json
import socket
import random

class PortManagement:
	def __init__(self):
		self.ports = []
	def check_port(self,port):
		return port in self.ports
	def new_port(self):
		available_ports = [ i for i in range(1024, 49151) if i not in self.ports and PortManagement.available(i) ]

		if len(available_ports) == 0: return False

		choosen = random.choice(available_ports)
		self.ports.append(choosen)
		return choosen
	def available(i):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		result = sock.connect_ex(('127.0.0.1',i))
		return result == 0

class Etcd:
	def __init__(self):
		self.api_url = "http://127.0.0.1:2379/v2"
	def get(self,key):
		return self._request(os.path.join("/keys",key))
	def set(self,key,data):
		return self._request(os.path.join("/keys",key),urllib.urlencode({ "value": data }))
	def _request(self,url,data=None):
		req = urllib2.Request(self.api_url+url, data)
		if data:
			req.get_method = lambda: "PUT"
		response = urllib2.urlopen(req)
		return json.load(response)

script = sys.argv[0].split("/")[-1]
name = ".".join(script.split(".")[:-1])
table = "urls"
database = name
script_dir = "/usr/local/bin/"+name+"-dir/"
extra_services_conf_file = name+"/services.json"
cronjob_conf_file = name+"/marathons"
backends_directory = name+"/backends"
cronjob_dir = "/etc/cron.d/"
cronjob = cronjob_dir+name
script_path = script_dir+script
conf_file = "haproxy.cfg"
etcd = Etcd()
port_management = PortManagement()

# Creates the cron job that will run each minute
# Installs the script
def createCronJob():
	try:
		os.makedirs(script_dir)
	except:
		pass
	try:
		os.mkdir(cronjob_dir)
	except: 
		pass
	with open(cronjob,"w") as f:
		f.write(cronContent())
	shutil.copyfile(script,script_path)
	os.chmod(script_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

# Updates the configuration of haproxy
# Forces restart
def updateConfig():
	masters = etcd.get(cronjob_conf_file)["node"]["value"]
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

	print subprocess.Popen("/bin/bash -c '/usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -p /var/run/haproxy-private.pid"+pids_string+"'", shell=True, stdout=subprocess.PIPE)

# Configurate the available apps using the provided masters url list
def configApps(masters):
	masters = masters.split("\n");

	apps = {}
	apps_data = etcd.get(extra_services_conf_file)
	for i in json.loads(apps_data["node"]["value"]):
		apps[i["app_name"]] = i

	content = []
	for master in masters:
		req = urllib2.Request("http://"+master+"/v2/tasks", None, { "Accept": "text/plain" })
		response = urllib2.urlopen(req)
		lines = response.read().split("\n")
		for line in lines:
			if line.strip() == "": continue
			parts = line.split("\t")
			app_name = parts[0]
			service_port = parts[1]
			servers = parts[2:]
			
			if app_name in apps:
				apps[app_name] = { "url": apps[app_name]["url"], "app_name": app_name, "service_port": service_port, "servers": servers}
			else:
				if port_management.check_port(service_port):
					service_port = port_management.new_port()
					if not service_port:
						raise Exception("No open port available")
				else:
					port_management.ports.append(service_port)
				server_config = listenAppFromPort(app_name,service_port,servers)
				content += server_config
				backend = socket.gethostbyname(socket.gethostname())+":"+service_port
				etcd.set(os.path.join(backends_directory,app_name),backend)

	if len(apps) > 0: content += listenAppFromUrl(apps)
	return content

# Creates the configuration for the apps received by parameter 
# Using acl and DNS matching
def listenAppFromUrl(apps):
	frontends = [ 
		"",
		"# Configuration for all the apps that are accessible using acl and custom DNS names",
		"frontend http-in",
		"   bind 0.0.0.0:80",
		"   mode http",
		"   option tcplog"
	]
	ifs = []
	backends = []

	for app_name,app in apps.items():
		if "servers" not in app: continue
		frontend = ""
		if(app["url"][0] == "/"): frontend = "   acl "+app_name+" path_end -i "+app["url"]
		else: frontend = "   acl "+app_name+" hdr(host) -i "+app["url"]

		frontends.append(frontend)
		ifs.append("use_backend srvs_"+app_name+"    if "+app_name)
		backend = [
			"",
			"# Backend of the app "+app_name,
			"backend srvs_"+app_name,
			"   mode http",
			#"   option httpclose",
			#"   option forwardfor",
			"   balance leastconn"
		]
		for s in range(len(app["servers"])):
			server = app["servers"][s]
			if server.strip() == "": continue
			backend.append("   server "+app_name+"-host"+str(s)+" "+server)
		etcd.set(os.path.join(backends_directory,app_name),app["url"])
		backends = backends + backend
	
	apps = frontends + ifs
	apps = apps + backends
	return apps

# Creates configuration for an app using a port to reach
def listenAppFromPort(app_name,service_port,servers):
	server_config = [
		"",
		"# Configuration for the app "+app_name,
		"# Using port "+service_port,
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

# Returns the content of the cron file
def cronContent():
	return "* * * * * root python "+script_path+" updateConfig >>/tmp/haproxycron.log 2>&1\n"

# Returns the global part of the app
def configHeader():
	header = [
		"# General section with all the global values. ",
		"# Added at method configHeader at haproxy-marathon-bridge",
		"global",
		"  daemon",
		#"  nbproc 2",
		"  pidfile /var/run/haproxy-private.pid",
		"  log 127.0.0.1 local0",
		"  log 127.0.0.1 local1 notice",
		"  maxconn 100000",
		"",
		"defaults",
		"  log            global",
		"  retries             30000",
		"  maxconn          150000",
		"  timeout connect  150000",
		"  timeout client  150000",
		"  timeout server  150000",
		"  option httplog",
		"  option dontlognull",
		#"  option forwardfor",
		#"  option http-server-close",
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
