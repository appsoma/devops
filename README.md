# devops
This repo contains install scripts to setup operating environments for Appsoma servers.

## Install Ansible

Below are the simple instructions. If you need more, try the [official docs](http://docs.ansible.com/intro_installation.html).

On Ubuntu:
```
$ sudo apt-get install software-properties-common
$ sudo apt-add-repository ppa:ansible/ansible
$ sudo apt-get update
$ sudo apt-get install ansible
```

On CentOS/Redhat:
If you don't have it, [configure EPEL](http://fedoraproject.org/wiki/EPEL).
```
$ sudo yum install ansible
```

On Mac OSX:
```
$ sudo easy_install pip
$ sudo pip install ansible
```

## Install Mesos for use with Welder

lorem ipsum
