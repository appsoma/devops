var ws = require("nodejs-websocket");
var request = require("request");

request("http://127.0.0.1:2379/v2/keys/haproxy-marathon-bridge/backends/echo-server-1",function(error,response,body) {
body = JSON.parse(body);
var conn = ws.connect("ws://"+body["node"]["value"]);

conn.on("text",function(str) {
	console.log("> "+str);
});

setInterval(function() {
	console.log("< hola");
	conn.sendText("hola");
},1000);
});
