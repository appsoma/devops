var express = require('express');
var app = express();
var process = require("process");

app.get('/', function (req, res) {
  res.send('Hello World! '+process.pid);
});

var server = app.listen(31111, function () {
  var host = server.address().address;
  var port = server.address().port;
  console.log('Example app listening at http://%s:%s', host, port);
});
