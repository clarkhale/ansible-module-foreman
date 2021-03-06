#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Ansible module to manage Foreman subnet resources.
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: foreman_architecture
short_description: Manage Foreman Architectures using Foreman API v2
description:
- Create and delete Foreman Architectures using Foreman API v2
options:
  name:
    description: Subnet name
    required: True
  network:
    description: Subnet network
    required: False
    default: None
  mask:
    description: Netmask for this subnet
    required: False
    default: None
  gateway:
    description: Gateway for this subnet
    required: False
    default: None
  dns_primary:
    description: Primary DNS for this subnet
    required: False
    default: None
  dns_secondary:
    description: Secondary DNS for this subnet
    required: False
    default: None
  domains:
    description: Domains in which this subnet is part
    required: False
    default: None
  ipam:
    description: Enable IP Address auto suggestion for this subnet
    required: False
    default: None
    choices: ['DHCP', 'Internal DB', 'Random DB', 'None']),
  boot_mode:
    description: Default boot mode for interfaces assigned to this subnet
    required: False
    default: 'DHCP'
    choices: ['DHCP', 'Static']),
  ip_from:
    description: Starting IP Address for IP auto suggestion
    required: False
    default: None
  ip_to:
    description: Ending IP Address for IP auto suggestion
    required: False
    default: None
  dhcp_proxy:
    description: DHCP smart proxy to use for this subnet
    required: False
    default: None
  dns_proxy:
    description: DNS smart proxy to use for this subnet
    required: False
    default: None
  discovery_proxy:
    description: Discovery smart proxy to use for this subnet (requires foreman discover plugin)
    required: False
    default: None
  tftp_proxy:
    description: TFTP smart proxy to use for this subnet
    required: False
    default: None
  state:
    description: State of subnet
    required: false
    default: present
    choices: ["present", "absent"]
  vlanid:
    description: VLAN ID for this subnet
    required: False
    default: None
  locations: List of locations the subnet should be assigned to
    required: false
    default: None
  organizations: List of organizations the subnet should be assigned to
    required: false
    default: None
  foreman_host:
    description: Hostname or IP address of Foreman system
    required: false
    default: 127.0.0.1
  foreman_port:
    description: Port of Foreman API
    required: false
    default: 443
  foreman_user:
    description: Username to be used to authenticate on Foreman
    required: true
  foreman_pass:
    description: Password to be used to authenticate user on Foreman
    required: true
  foreman_ssl:
    description: Enable SSL when connecting to Foreman API
    required: false
    default: true
notes:
- Requires the python-foreman package to be installed. See https://github.com/Nosmoht/python-foreman.
version_added: "2.0"
author: "Thomas Krahn (@nosmoht)"
'''

EXAMPLES = '''
- name: Ensure Subnet
  foreman_subnet:
    name: MySubnet
    network: 192.168.123.0
    mask: 255.255.255.0
    dns_primary: 192.168.123.1
    dns_secondary: 192.168.123.2
    domains:
      - foo.example.com
    ipam: DHCP
    boot_mode: Static
    ip_from: 192.168.123.3
    ip_to: 192.168.123.253
    gateway: 192.168.123.254
    vlanid: 123
    state: present
    locations:
    - Tardis
    organizations:
    - Dalek Inc
    - Cybermen
    foreman_host: 127.0.0.1
    foreman_port: 443
    foreman_user: admin
    foreman_pass: secret
'''

try:
    from foreman.foreman import *
except ImportError:
    foremanclient_found = False
else:
    foremanclient_found = True

try:
    from ansible.module_utils.foreman_utils import *

    has_import_error = False
except ImportError as e:
    has_import_error = True
    import_error_msg = str(e)


def domains_equal(data, subnet):
    data_domains = list(map(lambda d: d['name'], data['domains'])).sort()
    subnet_domains = list(map(lambda d: d['name'], subnet['domains'])).sort()
    if data_domains != subnet_domains:
        return False
    return True


def subnets_equal(data, subnet):
    comparable_keys = ['name', 'dns_primary', 'dns_secondary', 'gateway', 'ipam', 'boot_mode', 'mask', 'network',
                       'vlanid', 'from', 'to', 'tftp_id', 'dns_id', 'dhcp_id', 'discovery_id']
    if not all(data.get(key, None) == subnet.get(key, None) for key in comparable_keys):
        return False
    if not domains_equal(data, subnet):
        return False
    if not organizations_equal(data, subnet):
        return False
    if not locations_equal(data, subnet):
        return False
    return True


def get_resources(resource_type, resource_specs, theforeman):
    result = []
    for item in resource_specs:
        search_data = dict()
        if isinstance(item, dict):
            for key in item:
                search_data[key] = item[key]
        else:
            search_data['name'] = item
        try:
            resource = theforeman.search_resource(resource_type=resource_type, data=search_data)
            if not resource:
                module.fail_json(
                    msg='Could not find resource type {resource_type} defined as {spec}'.format(
                        resource_type=resource_type,
                        spec=item))
            result.append(resource)
        except ForemanError as e:
            module.fail_json(msg='Could not search resource type {resource_type} defined as {spec}: {error}'.format(
                resource_type=resource_type, spec=item, error=e.message))
    return result


def prepare_data(data, module, theforeman):
    for key in ['dns_primary', 'dns_secondary', 'gateway', 'ipam', 'boot_mode', 'mask', 'network',
                'vlanid', 'domains']:
        if key in module.params:
            data[key] = module.params[key]
    if 'ip_from' in module.params:
        data['from'] = module.params['ip_from']
    if 'ip_to' in module.params:
        data['to'] = module.params['ip_to']
    if 'domains' in module.params and module.params['domains']:
        data['domains'] = get_resources(resource_type='domains', resource_specs=module.params['domains'],
                                        theforeman=theforeman)
    for proxy_type in ['dns', 'dhcp', 'tftp', 'discovery']:
        key = "{0}_proxy".format(proxy_type)
        if key in module.params:
            id_key = "{0}_id".format(proxy_type)
            if module.params[key]:
                data[id_key] = get_resources(resource_type='smart_proxies', resource_specs=[module.params[key]],
                                             theforeman=theforeman)[0].get('id')
            else:
                data[id_key] = None
    return data


def ensure(module):
    name = module.params['name']
    state = module.params['state']
    locations = module.params['locations']
    organizations = module.params['organizations']

    theforeman = init_foreman_client(module)

    data = {'name': name}

    try:
        subnet = theforeman.search_subnet(data=data)
        if subnet:
            subnet = theforeman.get_subnet(id=subnet.get('id'))
    except ForemanError as e:
        module.fail_json(msg='Could not get subnet: {0}'.format(e.message))

    if organizations:
        data['organization_ids'] = get_organization_ids(module, theforeman, organizations)

    if locations:
        data['location_ids'] = get_location_ids(module, theforeman, locations)

    data = prepare_data(data, module, theforeman)

    if not subnet and state == 'present':
        try:
            subnet = theforeman.create_subnet(data=data)
            return True, subnet
        except ForemanError as e:
            module.fail_json(msg='Could not create subnet: {0}'.format(e.message))

    if subnet:
        if state == 'absent':
            try:
                subnet = theforeman.delete_subnet(id=subnet.get('id'))
                return True, subnet
            except ForemanError as e:
                module.fail_json(msg='Could not delete subnet: {0}'.format(e.message))

        if not subnets_equal(data, subnet):
            try:
                subnet = theforeman.update_subnet(id=subnet.get('id'), data=data)
                return True, subnet
            except ForemanError as e:
                module.fail_json(msg='Could not update subnet: {0}'.format(e.message))

    return False, subnet


def main():
    global module

    module = AnsibleModule(
        argument_spec=dict(
            dhcp_proxy=dict(type='str', required=False),
            dns_proxy=dict(type='str', required=False),
            discovery_proxy=dict(type='str', required=False),
            dns_primary=dict(type='str', required=False),
            dns_secondary=dict(type='str', required=False),
            domains=dict(type='list', required=False),
            gateway=dict(type='str', required=False),
            name=dict(type='str', required=True),
            network=dict(type='str', required=False),
            mask=dict(type='str', required=False),
            ipam=dict(type='str', required=False, choices=['DHCP', 'Internal DB', 'Random DB', 'None']),
            boot_mode=dict(type='str', required=False, choices=['DHCP', 'Static'], default='DHCP'),
            ip_from=dict(type='str', required=False),
            ip_to=dict(type='str', required=False),
            state=dict(type='str', default='present', choices=['present', 'absent']),
            tftp_proxy=dict(type='str', required=False),
            vlanid=dict(type='str', default=None),
            locations=dict(type='list', required=False),
            organizations=dict(type='list', required=False),
            foreman_host=dict(type='str', default='127.0.0.1'),
            foreman_port=dict(type='str', default='443'),
            foreman_user=dict(type='str', required=True),
            foreman_pass=dict(type='str', required=True, no_log=True),
            foreman_ssl=dict(type='bool', default=True)
        ),
    )

    if not foremanclient_found:
        module.fail_json(msg='python-foreman module is required. See https://github.com/Nosmoht/python-foreman.')

    changed, subnet = ensure(module)
    module.exit_json(changed=changed, subnet=subnet)


from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
