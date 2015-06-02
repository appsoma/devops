#!/bin/bash
# Submit request to launch docker container
curl -X POST -H "Content-Type: application/json" mesos.appsoma.com:8080/v2/apps -d '
{
	"id": "/simple-webpage",
	"instances": 3,
	"cpus": 0.5,
	"mem": 256,
	"ports": [
		31111
	],
	"healthChecks": [
		{
			"path": "/",
			"protocol": "HTTP",
			"portIndex": 0,
			"gracePeriodSeconds": 300,
			"intervalSeconds": 10,
			"timeoutSeconds": 20,
			"maxConsecutiveFailures": 3
		}
	],
	"uris": [ "file:///home/oink54321/data/haproxy/simple_webpage.js" ],
	"cmd": "/home/oink54321/.nvm/v0.10.31/bin/npm install express process request && /home/oink54321/.nvm/v0.10.31/bin/node simple_webpage.js"
}'
