#!/usr/bin/env python3
from proxmoxer import ProxmoxAPI
from hurry.filesize import size, iec, verbose
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from termcolor import colored
from styleframe import StyleFrame
import sys, configparser, textwrap, re, logging
import pandas as pd


logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(levelname)s - %(message)s')
logging.disable(level=logging.DEBUG)

# ---- START: ----
# parse argument from command line
def parse_args():
	parser = ArgumentParser(
		add_help=True,
		formatter_class=RawDescriptionHelpFormatter,
		description=textwrap.dedent('''\
			##############################################################
			#     Connects to Proxmox cluster, reads node's and vm's     #
			#     characteristics from API, use [--vminfo] flag to       #
			#     generate excel table from this data and [-f] to        #
			#     point the specific file you want to write to.          #
			##############################################################
			'''))
	parser.add_argument("--cluster",
						help="Enter the Proxmox cluster name from config.",
						metavar='CLUSTER',
						required=True)
	parser.add_argument("--vminfo",
						help="Get all vms info and generate excel table.",
						action='store_true',
						required=False)
	parser.add_argument("-f",
						help="File name to write table to.",
						metavar='example.xlsx',
						required=False)
	args = vars(parser.parse_args())
	if not len(sys.argv) > 1:
		parser.print_help(sys.stderr)
		sys.exit(127)
	return args


# Read Proxmox cluster credentials from config file
def read_config():
	config = configparser.ConfigParser()
	config.read('.config.ini', encoding='UTF-8')
	return config


# Authorization on Proxmox cluster and getting its API
def get_api(cluster_name):
	c = read_config()
	proxmox_host = c.get(cluster_name, 'host')
	proxmox_user = c.get(cluster_name, 'user')
	passw = c.get(cluster_name, 'pass')
	proxmox = ProxmoxAPI(host=proxmox_host, user=proxmox_user, password=passw, verify_ssl=False)
	return proxmox


# Get all nodes from cluster and return max cores + max memory
def get_all_nodes(api, flag):
	nodes = []
	for node in api.cluster.resources.get(type='node'):
		nodes.append(node['node'])
	nodes.sort()
	if not flag:
		print("There are nodes in this cluster:")
		for node in api.cluster.resources.get(type='node'):
			print("\t{0} --- {1} CPU --- {2}".format(colored(node['node'], 'green'), size(node['maxcpu'], system=iec), size(node['maxmem'], system=iec)))
	return nodes


# Get all vms cpu from cluster
def get_all_vms_cpu(api, nodes):
	for node in nodes:
		cpu = 0
		for vm in api.cluster.resources.get(type='vm'):
			if node == vm['node'] and vm['status'] == 'running':
				cpu += vm['maxcpu']
		print("All allocated CPU on node {0} is: {1}".format(colored(node, 'green'), colored(size(cpu, system=iec), 'red')))


# Get all vms storage on scsi1 from cluster
def get_all_vm_storages(api):
	for node in api.nodes.get():
		for vmid in api.nodes(node['node']).qemu.get():
			configs = api.nodes(node['node']).qemu(vmid['vmid']).config.get()
			try:
				a = configs['scsi1']
				print(vmid['vmid'] + ': ' + ",".join(re.findall(r'size=(\d+)', a)))
				logging.warning(msg=f'Error!')
			except Exception:
				print("Error while read API")


# Get all vms ram from cluster
def get_all_vms_ram(api, nodes):
	for node in nodes:
		ram = 0
		for vm in api.cluster.resources.get(type='vm'):
			if node == vm['node'] and vm['status'] == 'running':
				ram += vm['maxmem']
		print("All allocated RAM on node {0} is: {1}".format(colored(node, 'green'),
		                                                     colored(size(ram, system=iec), 'red')))


# Read API and generate Excel table from data
def get_all_vms_info(api, nodes, filename):
	dfs = []
	df1 = {}
	ret_api = api.cluster.resources
	for node in nodes:
		df_node = pd.DataFrame([node]).T
		dfs.append(df_node)
		df1 = pd.concat(dfs, ignore_index=True)
		logging.debug(msg=f"Checked node {node}")
		for vm in ret_api.get(type='vm'):
			vm_ip = ''
			if node == vm['node'] and vm['status'] == "running":
				try:
					d = api.nodes(node).qemu(vm['vmid']).agent.get('network-get-interfaces')
					vm_ip = d['result'][1]['ip-addresses'][0]['ip-address']
				except Exception:
					vm_ip = "Agent disabled"
				configs = api.nodes(node).qemu(vm['vmid']).config.get()
				try:
					d = configs['scsi0']
					disk_type = re.findall(r'([\w-]+(?=:))', d)
					vol1 = re.findall(r'size=(\w+)', d)
					disk_os = disk_type[0] + " " + vol1[0]
				except Exception:
					disk_os = '---'
				try:
					a = configs['scsi1']
					d_type = re.findall(r'([\w-]+(?=:))', a)
					vol = re.findall(r'size=(\w+)', a)
					disk = d_type[0] + " " + vol[0]
				except Exception:
					disk = '---'
				df = pd.DataFrame([vm['vmid'], vm['name'], vm_ip, size(vm['maxmem'], system=iec), vm['maxcpu'], disk_os, disk, vm['status'], size(vm['mem'], system=iec), vm['cpu'] * 100]).T
				dfs.append(df)
				df1 = pd.concat(dfs, ignore_index=True)
	df1.rename(columns={0: 'VmID', 1: 'Hostname', 2: 'IP', 3: 'RAM', 4: 'CPU', 5: 'OS Storage', 6: 'Additional disk', 7: 'Status', 8: 'LA RAM', 9: 'LA CPU'}, inplace=True)
	writer = StyleFrame.ExcelWriter(filename)
	sf = StyleFrame(df1)
	sf.to_excel(excel_writer=writer, sheet_name='VMsList', index=False, best_fit=['VmID', 'Hostname', 'IP', 'OS Storage', 'Additional disk'],  freeze_panes=(1, 1), float_format="%.1f", verbose=True)
	writer.save()


# Main function
def main():
	args = parse_args()
	api = get_api(args['cluster'])
	if args['f']:
		filename = args['f']
	else:
		filename = 'vms.xlsx'
	if args['vminfo']:
		flag = 1
		nodes = get_all_nodes(api, flag)
		get_all_vms_info(api, nodes, filename)
		sys.exit(0)
	flag = 0
	nodes = get_all_nodes(api, flag)
	print(colored('\n##############################################\n', 'yellow'))
	get_all_vms_cpu(api, nodes)
	print(colored('\n##############################################\n', 'yellow'))
	get_all_vms_ram(api, nodes)


if __name__ == '__main__':
	main()

# vim: ft=python
