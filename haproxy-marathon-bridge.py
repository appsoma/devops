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
config_template = name+"/haproxy.cfg"
config_port_template = name+"/haproxy_port.cfg"
config_frontends_template = name+"/haproxy_frontends.cfg"
config_backend_template = name+"/haproxy_backend.cfg"
extra_services_conf_file = name+"/services.json"
cronjob_conf_file = name+"/marathons"
backends_directory = "internals"
externals_directory = "externals"
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
	config = "\n".join(configHeader().split("\n") + configApps(masters))
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
				external = urllib2.urlopen('http://whatismyip.org').read()+":"+service_port
				etcd.set(os.path.join(backends_directory,app_name),backend)
				etcd.set(os.path.join(externals_directory,app_name),external)

	if len(apps) > 0: content += listenAppFromUrl(apps)
	return content

# Creates the configuration for the apps received by parameter 
# Using acl and DNS matching
def listenAppFromUrl(apps):
	frontends = etcd.get(config_frontends_template)["node"]["value"]
	backend_template = etcd.get(config_backend_template)["node"]["value"]
	acls = []
	use_backends = []
	backends = []

	for app_name,app in apps.items():
		if "servers" not in app: continue
		frontend = ""
		if(app["url"][0] == "/"): frontend = "   acl "+app_name+" path_end -i "+app["url"]
		else: frontend = "   acl "+app_name+" hdr(host) -i "+app["url"]

		acls.append(frontend)
		use_backends.append("use_backend srvs_"+app_name+"    if "+app_name)
		servers = []
		for s in range(len(app["servers"])):
			server = app["servers"][s]
			if server.strip() == "": continue
			servers.append("   server "+app_name+"-host"+str(s)+" "+server)
		backends += backend_template.replace("$app_name",app_name).replace("$servers","\n".join(servers)).split("\n")
		etcd.set(os.path.join(backends_directory,app_name),app["url"])
		etcd.set(os.path.join(externals_directory,app_name),app["url"])
	
	apps = frontends.replace("$acls","".join(acls)).replace("$use_backends","".join(use_backends)).split("\n")
	apps = apps + backends
	return apps

# Creates configuration for an app using a port to reach
def listenAppFromPort(app_name,service_port,servers):
	server_config = etcd.get(config_port_template)["node"]["value"]
				.replace("$app_name",app_name)
				.replace("$service_port",service_port)
				.split("\n")

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
	return etcd.get(config_template)["node"]["value"]

if __name__ == "__main__":
	method = sys.argv[1]
	args = sys.argv[2:]

	if method in globals():
		globals()[method](*args)
	else:
		print "Wrong methods"
