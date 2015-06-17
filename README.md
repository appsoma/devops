# haproxy/marathon bridge

Bridge to deal with load balancing and service discovery on marathon using haproxy.

<a name='gettingstarted'></a>
# Getting Started

# Contents
* [Getting Started](#gettingstarted)
* [Installation](#installation)
* [Usage](#usage)
* [Service discovery](#servicediscovery)

<a name='installation'></a>
## Installing

```
wget https://raw.githubusercontent.com/appsoma/devops/master/haproxy-marathon-bridge.py
chmod +x haproxy-marathon-bridge.py
sudo ./haproxy-marathon-bridge.py createCronJob
```

<a name='usage'></a>
## Usage

```
sudo /usr/local/bin/haproxy-marathon-bridge-dir/haproxy-marathon-bridge.py listUrls #Lists the marathon services that are using a DNS name.
sudo /usr/local/bin/haproxy-marathon-bridge-dir/haproxy-marathon-bridge.py createCronJob #Creates the cronjob to update the configuration and restarts haproxy.
sudo /usr/local/bin/haproxy-marathon-bridge-dir/haproxy-marathon-bridge.py addUrl "app" "url" #Adds a new DNS name to a marathon app.
sudo /usr/local/bin/haproxy-marathon-bridge-dir/haproxy-marathon-bridge.py updateConfig $(cat /etc/haproxy/marathon/bridge/marathons) #Forces an updates of the configuration file and restarts haproxy.
```

From the moment you add a new entry to the configuration, it will take 1 minute max to be on available on haproxy.

### Adding services out of marathon

If you want to add DNS names to services not runninng on marathon, you should use the file /etc/haproxy-marathon-bridge/services.json. Is a json file with the following structure:

[
    {
        "url": "bluer.io",
        "service_port": "80",
        "app_name": "bluer",
        "servers": [ "54.165.117.212:8898" ]
    }
]

Url is the DNS name, service port the port in which you want it running, app_name it's just an ID name (not useful at all) and servers is the list of servers to loadbalance. 

<a name='servicediscovery'></a>
## Service discovery

If an app on marathon was configured to use a DNS, will use acl and http on haproxy to work with that. You can reach it by the DNS name.

If an app on marathon wasn't configure to use a DNS, will use a backend on tcp under the port of the app in the master of marathon. THat means, if you start an app on marathon and don't assign a DNS, you can reach to it by:

master-marathon-url:port-number

haproxy load balances the request using leastconn method.
