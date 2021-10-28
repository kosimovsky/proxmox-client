# Usage
```
$ python3 proxmox-client.py -h
usage: proxmox-client.py [-h] --cluster CLUSTER [--vminfo] [-f example.xlsx]

##############################################################
#     Connects to Proxmox cluster, reads node's and vm's     #
#     characteristics from API, use [--vminfo] flag to       #
#     generate excel table from this data and [-f] to        #
#     point the specific file you want to write to.          #
##############################################################

optional arguments:
  -h, --help         show this help message and exit
  --cluster CLUSTER  Enter the Proxmox cluster name from config.
  --vminfo           Get all vms info and generate excel table.
  -f example.xlsx    File name to write table to.
