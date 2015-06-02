#!/usr/bin/env node

// TODO: (ACB) Find a way to deal properly with global dependencies
var fs = require("/usr/lib/node_modules/fs-extra"),
	process = require("/usr/lib/node_modules/process"),
	exec = require('child_process').exec,
	request = require("/usr/lib/node_modules/request"),
	sqlite3 = require('/usr/lib/node_modules/sqlite3').verbose();

require('/usr/lib/node_modules/scribe-js')();
var console = process.console;

var script = process.argv[1].split("/").pop();
var name = script.split(".");
name = name.slice(0,name.length-1).join(".");
var table = "urls";
var database = name;
var database_path = "/usr/local/bin/"+name+"/"+name;
var cronjob_conf_file = "/etc/"+name+"/marathons";
var cronjob_dir = "/etc/cron.d/";
var cronjob = cronjob_dir+name;
var script_dir = "/usr/local/bin/"+name+"/";
var script_path = script_dir+script;
var conf_file = "haproxy.cfg";

var methods = {
	createDB: function(db_path) {
		if(!db_path) var db_path = database_path;
		db = new sqlite3.Database(db_path);

		var values = { url: "varchar(255)", app: "varchar(255)" }
		var cols = []
		for(var k in values) {
			cols.push([k,values[k]].join(" "));
		}
		db.run("CREATE TABLE IF NOT EXISTS "+table+" ("+cols.join(",")+")");
	
		db.close();
	},
	createCronJob: function() {
		fs.mkdirsSync(script_dir);
		this.createDB(database_path);
		
		fs.mkdir(cronjob_dir);
		file = fs.createWriteStream(cronjob);
		file.write(this.cronContent());
		file.close();
		fs.copySync(script,script_path);
		fs.chmodSync(script_path,"744");
		//this.updateConfig();
	},
	updateConfig: function(masters) {
		this.configApps(masters,(function(app_config) {
			var config = this.configHeader().concat(app_config).join("\n");
			var file = fs.createReadStream("/etc/haproxy/"+conf_file);

			var content = file.read();
			file.close();
			if(content != config) {
				file = fs.createWriteStream("/etc/haproxy/"+conf_file);
				file.write(config);
				file.close();
				exec("/bin/bash -c 'haproxy -f /etc/haproxy/haproxy.cfg -p /var/run/haproxy-private.pid -sf $(</var/run/haproxy-private.pid)'");
			}
		}).bind(this));
	},
	configApps: function(masters,cb) {
		db = new sqlite3.Database(database_path);
		masters = masters.split("\n");

		db.serialize((function() {
			db.all("SELECT * FROM "+table,(function(err,rows) {
				if(err) throw err;

				var apps = {};
				for(var i in rows) {
					apps[rows[i].app] = rows[i];
				}
				
				for(var i in masters) {
					var master = masters[i];
					request({ url: "http://"+master+"/v2/tasks", headers: { Accept: "text/plain" }},(function(err,res,body) {
						var lines = body.split("\n");
						var content = [];
						var appsWithUrl = [];
						for(var l in lines) {
							if(lines[l].trim() == "") continue;
							var parts = lines[l].split("\t");
							var app_name = parts[0];
							var service_port = parts[1];
							var servers = parts.slice(2);
							if(apps[app_name]) {
								appsWithUrl.push({
									url: apps[app_name].url,
									app_name: app_name,
									service_port: service_port,
									servers: servers
								});
								continue;
							}
							var server_config = this.listenAppFromPort(app_name,service_port,servers);
							content = content.concat(server_config);
						}
						if(appsWithUrl.length) content = content.concat(this.listenAppFromUrl(appsWithUrl));
						cb(content);
					}).bind(this));
				}
			}).bind(this));
		}).bind(this));
	
		db.close();
	},
	listenAppFromUrl: function(apps) {
		var frontends = [ "frontend http" ];
		var ifs = [];
		var backends = [];

		for(var i in apps) {
			var app = apps[i];
			var app_name = app.app_name;
			var frontend = "";
			if(app.url[0] == "/") {
				frontend = "acl "+app_name+" path_end -i "+app.url;
			} else {
				frontend = "acl "+app_name+" hdr_beg(host) -i "+app.url;
			}
			frontends.push(frontend);
			ifs.push("use_backend srvs_"+app_name+"    if "+app_name);
			var backend = [
				"backend srvs_"+app_name,
				"   mode tcp",
				"   option tcplog",
				"   balance leastconn",
			];
			for(var s in app.servers) {
				var server = app.servers[s];
				if(server.trim() == "") continue;
				backend.push("   server host"+s+" "+server);
			}

			backends = backends.concat(backend);
		}
		
		var apps = frontends.concat(ifs);
		apps = apps.concat(backends);
		return apps;
	},
	listenAppFromPort: function(app_name,service_port,servers) {
		var server_config = [
			"listen "+app_name+"-"+service_port,
			"  bind 0.0.0.0:"+service_port,
			"  mode tcp",
			"  option tcplog",
			"  balance leastconn"
		];
	
		for(var i in servers) {
			var server = servers[i];
			if(server.trim() == "") continue;
			server_config.push("  server "+app_name+"-"+i+" "+server+" check");
		}
		return server_config;
	},
	cronContent: function() {
		return "* * * * * root "+script_path+" updateConfig $(cat "+cronjob_conf_file+")";
	},
	configHeader: function() {
		var header = [
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
		];
		return header;
	}
};

if(process.argv.length > 1) {
	var method = process.argv[2];
	var args = process.argv.slice(3);

	if(methods[method]) {
		methods[method].apply(methods,args);
	} else {
		console.time().file().error("Wrong methods");
	}
}
