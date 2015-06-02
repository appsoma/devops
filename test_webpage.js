var request = require("request");

var url = "mesos.appsoma.com:31111";

console.log("VAMOS");
setInterval(function() {
	request('http://'+url, function (error, response, body) {
		if (!error && response.statusCode == 200) {
			console.log(body);
		} else {
			console.log("PROBLEM",error);
			if(response) console.log("CODE",response.statusCode);
		}
	});
},50);
