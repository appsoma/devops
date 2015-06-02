var ws = require("nodejs-websocket");

var url = "mesos.appsoma.com:31336";

function connect() {
	var c = ws.connect("ws://"+url);

	c.on("text",function(str) { console.log("Text received",str); });
	return c;
}

var c = connect();
setInterval(function() {
	try{
		c.sendText("hola");
	} catch(err) {
		c = connect();
	}
},1000);
