# Copyright 2014 Huawei Technologies Co. Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Database model"""
import datetime
import logging
import netaddr
import simplejson as json

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import ColumnDefault
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import relationship, backref
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator
from sqlalchemy import UniqueConstraint

from compass.db import exception
from compass.db import validator
from compass.utils import util


BASE = declarative_base()


class JSONEncoded(TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""

    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class TimestampMixin(object):
    created_at = Column(DateTime, default=lambda: datetime.datetime.now())
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(),
                        onupdate=lambda: datetime.datetime.now())


class HelperMixin(object):
    def initialize(self):
        self.update()

    def update(self):
        pass

    def validate(self):
        pass

    def to_dict(self):
        keys = self.__mapper__.columns.keys()
        dict_info = {}
        for key in keys:
            value = getattr(self, key)
            if value is not None:
                if isinstance(value, datetime.datetime):
                    value = util.format_datetime(value)
                dict_info[key] = value
        return dict_info


class MetadataMixin(HelperMixin):
    name = Column(String(80))
    display_name = Column(String(80))
    path = Column(String(256))
    description = Column(Text)
    is_required = Column(Boolean, default=False)
    required_in_whole_config = Column(Boolean, default=False)
    mapping_to = Column(String(80), default='')
    validator_data = Column('validator', Text)
    js_validator = Column(Text)
    default_value = Column(JSONEncoded)
    options = Column(JSONEncoded, default=[])
    required_in_options = Column(Boolean, default=False)

    def initialize(self):
        if not self.display_name:
            if self.name:
                self.display_name = self.name
        super(MetadataMixin, self).initialize()

    @property
    def validator(self):
        if not self.name:
            raise exception.InvalidParamter(
                'name is not set in os metadata %s' % self.id
            )
        if not self.validator_data:
            return None
        func = eval(
            self.validator_data,
            validator.VALIDATOR_GLOBALS,
            validator.VALIDATOR_LOCALS
        )
        if not callable(func):
            raise Exception(
                '%s is not callable' % self.validator_data
            )
        return func

    @validator.setter
    def validator(self, value):
        if not value:
            self.validator_data = None
        elif isinstance(value, basestring):
            self.validator_data = value
        elif callable(value):
            self.validator_data = value.func_name
        else:
            raise Exception(
                '%s is not callable' % value
            )

    def to_dict(self):
        self_dict_info = {}
        if self.field:
            self_dict_info.update(self.field.to_dict())
        else:
            self_dict_info['field_type_data'] = 'dict'
            self_dict_info['field_type'] = dict
        self_dict_info.update(super(MetadataMixin, self).to_dict())
        validator = self.validator
        if validator:
            self_dict_info['validator_data'] = self.validator_data
            self_dict_info['validator'] = validator
        js_validator = self.js_validator
        if js_validator:
            self_dict_info['js_validator'] = js_validator
        dict_info = {
            '_self': self_dict_info
        }
        for child in self.children:
            dict_info.update(child.to_dict())
        return {
            self.name: dict_info
        }
        return dict_info


class FieldMixin(HelperMixin):
    id = Column(Integer, primary_key=True)
    field = Column(String(80), unique=True)
    field_type_data = Column(
        'field_type',
        Enum('basestring', 'int', 'float', 'list', 'bool'),
        ColumnDefault('basestring')
    )
    display_type = Column(
        Enum(
            'checkbox', 'radio', 'select',
            'multiselect', 'combobox', 'text',
            'multitext', 'password'
        ),
        ColumnDefault('text')
    )
    validator_data = Column('validator', Text)
    js_validator = Column(Text)
    description = Column(Text)

    @property
    def field_type(self):
        if not self.field_type_data:
            return None
        field_type = eval(self.field_type_data)
        if not type(field_type) == type:
            raise Exception(
                '%s is not type' % self.field_type_data
            )
        return field_type

    @field_type.setter
    def field_type(self, value):
        if not value:
            self.field_type_data = None
        elif isinstance(value, basestring):
            self.field_type_data = value
        elif type(value) == type:
            self.field_type_data = value.__name__
        else:
            raise Exception(
                '%s is not type' % value
            )

    @property
    def validator(self):
        if not self.validator_data:
            return None
        func = eval(
            self.validator_data,
            validator.VALIDATOR_GLOBALS,
            validator.VALIDATOR_LOCALS
        )
        if not callable(func):
            raise Exception(
                '%s is not callable' % self.validator_data
            )
        return func

    @validator.setter
    def validator(self, value):
        if not value:
            self.validator_data = None
        elif isinstance(value, basestring):
            self.validator_data = value
        elif callable(value):
            self.validator_data = value.func_name
        else:
            raise Exception(
                '%s is not callable' % value
            )

    def to_dict(self):
        dict_info = super(FieldMixin, self).to_dict()
        dict_info['field_type'] = self.field_type
        validator = self.validator
        if validator:
            dict_info['validator'] = self.validator
        js_validator = self.js_validator
        if js_validator:
            dict_info['js_validator'] = self.js_validator
        return dict_info


class InstallerMixin(HelperMixin):
    name = Column(String(80))
    instance_name = Column(String(80), unique=True)
    settings = Column(MutableDict.as_mutable(JSONEncoded), default={})

    def validate(self):
        if not self.name:
            raise exception.InvalidParameter(
                'name is not set in installer %s' % self.instance_name
            )
        super(InstallerMixin, self).validate()


class StateMixin(TimestampMixin, HelperMixin):
    state = Column(
        Enum(
            'UNINITIALIZED', 'INITIALIZED',
            'INSTALLING', 'SUCCESSFUL', 'ERROR'
        ),
        ColumnDefault('UNINITIALIZED')
    )
    percentage = Column(Float, default=0.0)
    message = Column(Text, default='')
    severity = Column(
        Enum('INFO', 'WARNING', 'ERROR'),
        ColumnDefault('INFO')
    )

    def update(self):
        if self.state in ['UNINITIALIZED', 'INITIALIZED']:
            self.percentage = 0.0
            self.severity = 'INFO'
            self.message = ''
        if self.state == 'INSTALLING':
            if self.severity == 'ERROR':
                self.state = 'ERROR'
            elif self.percentage >= 1.0:
                self.state = 'SUCCESSFUL'
                self.percentage = 1.0
        if self.state == 'SUCCESSFUL':
            self.percentage = 1.0
        super(StateMixin, self).update()


class HostNetwork(BASE, TimestampMixin, HelperMixin):
    """Host network table."""
    __tablename__ = 'host_network'

    id = Column(Integer, primary_key=True)
    host_id = Column(
        Integer,
        ForeignKey('host.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    interface = Column(
        String(80))
    subnet_id = Column(
        Integer,
        ForeignKey('network.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    ip_int = Column(BigInteger, unique=True)
    is_mgmt = Column(Boolean, default=False)
    is_promiscuous = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint('host_id', 'interface', name='constraint'),
    )

    def __init__(self, host_id, interface, **kwargs):
        self.host_id = host_id
        self.interface = interface
        super(HostNetwork, self).__init__(**kwargs)

    @property
    def ip(self):
        return str(netaddr.IPAddress(self.ip_int))

    @ip.setter
    def ip(self, value):
        self.ip_int = int(netaddr.IPAddress(value))

    @hybrid_property
    def subnet(self):
        return self.network.subnet

    @subnet.expression
    def subnet(cls):
        return cls.network.subnet

    @property
    def netmask(self):
        return str(netaddr.IPNetwork(self.subnet).netmask)

    def validate(self):
        if not self.network:
            raise exception.InvalidParameter(
                'subnet is not set in %s interface %s' % (
                    self.host_id, self.interface
                )
            )
        if not self.ip_int:
            raise exception.InvalidParameter(
                'ip is not set in %s interface %s' % (
                    self.host_id, self.interface
                )
            )
        try:
            netaddr.IPAddress(self.ip_int)
        except Exception:
            raise exception.InvalidParameter(
                'ip %s format is uncorrect in %s interface %s' % (
                    self.ip_int, self.host_id, self.interface
                )
            )
        ip = netaddr.IPAddress(self.ip_int)
        subnet = netaddr.IPNetwork(self.subnet)
        if ip not in subnet:
            raise exception.InvalidParameter(
                'ip %s is not in subnet %s' % (
                    str(ip), str(subnet)
                )
            )
        super(HostNetwork, self).validate()

    def to_dict(self):
        dict_info = super(HostNetwork, self).to_dict()
        dict_info['ip'] = self.ip
        dict_info['interface'] = self.interface
        dict_info['netmask'] = self.netmask
        dict_info['subnet'] = self.subnet
        return dict_info


class ClusterHostState(BASE, StateMixin):
    """ClusterHost state table."""
    __tablename__ = 'clusterhost_state'

    id = Column(
        Integer,
        ForeignKey('clusterhost.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )

    def update(self):
        host_state = self.host.state
        if self.state == 'INITIALIZED':
            if host_state.state in ['UNINITIALIZED']:
                host_state.state = 'INITIALIZED'
                host_state.update()
        elif self.state == 'INSTALLING':
            if host_state.state in ['UNINITIALIZED', 'INITIALIZED']:
                host_state.state = 'INSTALLING'
                host_state.update()
        super(ClusterHostState, self).update()


class ClusterHost(BASE, TimestampMixin, HelperMixin):
    """ClusterHost table."""
    __tablename__ = 'clusterhost'

    id = Column(Integer, primary_key=True)
    cluster_id = Column(
        Integer,
        ForeignKey('cluster.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    host_id = Column(
        Integer,
        ForeignKey('host.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    config_step = Column(String(80), default='')
    package_config = Column(JSONEncoded, default={})
    config_validated = Column(Boolean, default=False)
    deployed_package_config = Column(JSONEncoded, default={})

    __table_args__ = (
        UniqueConstraint('cluster_id', 'host_id', name='constraint'),
    )

    state = relationship(
        ClusterHostState,
        uselist=False,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('host')
    )

    def __init__(self, cluster_id, host_id, **kwargs):
        self.cluster_id = cluster_id
        self.host_id = host_id
        self.state = ClusterHostState()
        super(ClusterHost, self).__init__(**kwargs)

    def update(self):
        if self.host.reinstall_os:
            if self.state in ['SUCCESSFUL', 'ERROR']:
                if self.config_validated:
                    self.state.state = 'INITIALIZED'
                else:
                    self.state.state = 'UNINITIALIZED'
                self.state.update()

    @property
    def name(self):
        return '%s.%s' % (self.host.name, self.cluster.name)

    @property
    def patched_package_config(self):
        return self.package_config

    @patched_package_config.setter
    def patched_package_config(self, value):
        self.package_config = util.merge_dict(dict(self.package_config), value)
        logging.info(
            'patch clusterhost %s package config: %s',
            self.id, value
        )
        self.config_validated = False

    @property
    def put_package_config(self):
        return self.package_config

    @put_package_config.setter
    def put_package_config(self, value):
        package_config = dict(self.package_config)
        package_config.update(value)
        self.package_config = package_config
        logging.info(
            'put clusterhost %s package config: %s',
            self.id, value
        )
        self.config_validated = False

    @property
    def patched_os_config(self):
        return self.host.os_config

    @patched_os_config.setter
    def patched_os_config(self, value):
        host = self.host
        host.patched_os_config = value

    @property
    def put_os_config(self):
        return self.host.os_config

    @put_os_config.setter
    def put_os_config(self, value):
        host = self.host
        host.put_os_config = value

    @hybrid_property
    def distributed_system_name(self):
        return self.cluster.distributed_system_name

    @distributed_system_name.expression
    def distributed_system_name(cls):
        return cls.cluster.distributed_system_name

    @hybrid_property
    def os_name(self):
        return self.host.os_name

    @os_name.expression
    def os_name(cls):
        return cls.host.os_name

    @hybrid_property
    def clustername(self):
        return self.cluster.name

    @clustername.expression
    def clustername(cls):
        return cls.cluster.name

    @hybrid_property
    def hostname(self):
        return self.host.name

    @hostname.expression
    def hostname(cls):
        return cls.host.name

    @property
    def distributed_system_installed(self):
        return self.state.state == 'SUCCESSFUL'

    @property
    def resintall_os(self):
        return self.host.reinstall_os

    @property
    def reinstall_distributed_system(self):
        return self.cluster.reinstall_distributed_system

    @property
    def os_installed(self):
        return self.host.os_installed

    @property
    def roles(self):
        package_config = self.package_config
        if 'roles' in package_config:
            role_names = package_config['roles']
            roles = self.cluster.adapter.roles
            role_mapping = {}
            for role in roles:
                role_mapping[role.name] = role
            filtered_roles = []
            for role_name in role_names:
                if role_name in role_mapping:
                    filtered_roles.append(role_mapping[role_name])
            return filtered_roles
        else:
            return None

    @hybrid_property
    def owner(self):
        return self.cluster.owner

    @owner.expression
    def owner(cls):
        return cls.cluster.owner

    def state_dict(self):
        cluster = self.cluster
        host = self.host
        if (
            not cluster.distributed_system or
            host.state.state != 'SUCCESSFUL'
        ):
            return host.state_dict()
        return self.state.to_dict()

    def to_dict(self):
        dict_info = self.host.to_dict()
        dict_info.update(super(ClusterHost, self).to_dict())
        dict_info.update({
            'distributed_system_name': self.distributed_system_name,
            'distributed_system_installed': self.distributed_system_installed,
            'reinstall_distributed_system': self.reinstall_distributed_system,
            'owner': self.owner,
            'clustername': self.clustername,
            'hostname': self.hostname,
            'name': self.name,
            'roles': [role.to_dict() for role in self.roles]
        })
        return dict_info


class HostState(BASE, StateMixin):
    """Host state table."""
    __tablename__ = 'host_state'

    id = Column(
        Integer,
        ForeignKey('host.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )

    def update(self):
        host = self.host
        if self.state == 'INSTALLING':
            host.reinstall_os = False
            for clusterhost in self.host.clusterhosts:
                if clusterhost.state in [
                    'SUCCESSFUL', 'ERROR'
                ]:
                    clusterhost.state = 'INSTALLING'
                    clusterhost.state.update()
        elif self.state == 'UNINITIALIZED':
            for clusterhost in self.host.clusterhosts:
                if clusterhost.state in [
                    'INITIALIZED', 'INSTALLING', 'SUCCESSFUL', 'ERROR'
                ]:
                    clusterhost.state = 'UNINITIALIZED'
                    clusterhost.state.update()
        elif self.state == 'INITIALIZED':
            for clusterhost in self.host.clusterhosts:
                if clusterhost.state in [
                    'INSTALLING', 'SUCCESSFUL', 'ERROR'
                ]:
                    clusterhost.state = 'INITIALIZED'
                    clusterhost.state.update()
        super(HostState, self).update()


class Host(BASE, TimestampMixin, HelperMixin):
    """Host table."""
    __tablename__ = 'host'

    name = Column(String(80), unique=True)
    os_id = Column(Integer, ForeignKey('os.id'))
    config_step = Column(String(80), default='')
    os_config = Column(JSONEncoded, default={})
    config_validated = Column(Boolean, default=False)
    deployed_os_config = Column(JSONEncoded, default={})
    os_name = Column(String(80))
    creator_id = Column(Integer, ForeignKey('user.id'))
    id = Column(
        Integer,
        ForeignKey('machine.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )
    reinstall_os = Column(Boolean, default=True)

    host_networks = relationship(
        HostNetwork,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('host')
    )
    clusterhosts = relationship(
        ClusterHost,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('host')
    )
    state = relationship(
        HostState,
        uselist=False,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('host')
    )

    @hybrid_property
    def mac(self):
        machine = self.machine
        if machine:
            return machine.mac
        else:
            return None

    @property
    def patched_os_config(self):
        return self.os_config

    @patched_os_config.setter
    def patched_os_config(self, value):
        self.os_config = util.merge_dict(dict(self.os_config), value)
        logging.info('patch host os config in %s: %s', self.id, value)
        self.config_validated = False

    @property
    def put_os_config(self):
        return self.os_config

    @put_os_config.setter
    def put_os_config(self, value):
        os_config = dict(self.os_config)
        os_config.update(value)
        self.os_config = os_config
        logging.info('put host os config in %s: %s', self.id, value)
        self.config_validated = False

    def __init__(self, id, **kwargs):
        self.id = id
        self.state = HostState()
        super(Host, self).__init__(**kwargs)

    def initialize(self):
        if not self.name:
            self.name = str(self.id)
        super(Host, self).initialize()

    def update(self):
        if self.reinstall_os:
            if self.state in ['SUCCESSFUL', 'ERROR']:
                if self.config_validated:
                    self.state.state = 'INITIALIZED'
                else:
                    self.state.state = 'UNINITIALIZED'
                self.state.update()
        os = self.os
        if os:
            self.os_name = os.name
        else:
            self.os_name = None
        super(Host, self).update()

    def validate(self):
        os = self.os
        if not os:
            raise exception.InvalidParameter(
                'os is not set in host %s' % self.id
            )
        if not os.deployable:
            raise exception.InvalidParameter(
                'os %s is not deployable' % os.name
            )
        creator = self.creator
        if not creator:
            raise exception.InvalidParameter(
                'creator is not set in host %s' % self.id
            )
        super(Host, self).validate()

    @hybrid_property
    def owner(self):
        return self.creator.email

    @owner.expression
    def owner(cls):
        return cls.creator.email

    @property
    def os_installed(self):
        return self.state.state == 'SUCCESSFUL'

    @property
    def clusters(self):
        return [clusterhost.cluster for clusterhost in self.clusterhosts]

    def state_dict(self):
        return self.state.to_dict()

    def to_dict(self):
        dict_info = self.machine.to_dict()
        dict_info.update(super(Host, self).to_dict())
        dict_info.update({
            'machine_id': self.machine.id,
            'owner': self.owner,
            'os_installed': self.os_installed,
            'networks': [
                host_network.to_dict()
                for host_network in self.host_networks
            ],
            'clusters': [cluster.to_dict() for cluster in self.clusters]
        })
        return dict_info


class ClusterState(BASE, StateMixin):
    """Cluster state table."""
    __tablename__ = 'cluster_state'

    id = Column(
        Integer,
        ForeignKey('cluster.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True
    )
    total_hosts = Column(
        Integer,
        default=0
    )
    installing_hosts = Column(
        Integer,
        default=0
    )
    completed_hosts = Column(
        Integer,
        default=0
    )
    failed_hosts = Column(
        Integer,
        default=0
    )

    def to_dict(self):
        dict_info = super(ClusterState, self).to_dict()
        dict_info['status'] = {
            'total_hosts': self.total_hosts,
            'installing_hosts': self.installing_hosts,
            'completed_hosts': self.completed_hosts,
            'failed_hosts': self.failed_hosts
        }
        return dict_info

    def update(self):
        cluster = self.cluster
        clusterhosts = cluster.clusterhosts
        self.total_hosts = len(clusterhosts)
        if self.state in ['UNINITIALIZED', 'INITIALIZED']:
            self.installing_hosts = 0
            self.failed_hosts = 0
            self.completed_hosts = 0
        if self.state == 'INSTALLING':
            cluster.reinstall_distributed_system = False
            if not cluster.distributed_system:
                for clusterhost in clusterhosts:
                    host = clusterhost.host
                    host_state = host.state.state
                    if host_state == 'INSTALLING':
                        self.intsalling_hosts += 1
                    elif host_state == 'ERROR':
                        self.failed_hosts += 1
                    elif host_state == 'SUCCESSFUL':
                        self.completed_hosts += 1
            else:
                for clusterhost in clusterhosts:
                    clusterhost_state = clusterhost.state.state
                    if clusterhost_state == 'INSTALLING':
                        self.intsalling_hosts += 1
                    elif clusterhost_state == 'ERROR':
                        self.failed_hosts += 1
                    elif clusterhost_state == 'SUCCESSFUL':
                        self.completed_hosts += 1
            if self.total_hosts:
                self.percentage = (
                    float(self.completed_hosts)
                    /
                    float(self.total_hosts)
                )
            self.message = (
                'toal %s, installing %s, complted: %s, error $s'
            ) % (
                self.total_hosts, self.completed_hosts,
                self.intsalling_hosts, self.failed_hosts
            )
            if self.failed_hosts:
                self.severity = 'ERROR'
        super(ClusterState, self).update()


class Cluster(BASE, TimestampMixin, HelperMixin):
    """Cluster table."""
    __tablename__ = 'cluster'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True)
    reinstall_distributed_system = Column(Boolean, default=True)
    config_step = Column(String(80), default='')
    os_id = Column(Integer, ForeignKey('os.id'), nullable=True)
    os_name = Column(String(80), nullable=True)
    distributed_system_id = Column(
        Integer, ForeignKey('distributed_system.id'),
        nullable=True
    )
    distributed_system_name = Column(
        String(80), nullable=True
    )
    os_config = Column(JSONEncoded, default={})
    package_config = Column(JSONEncoded, default={})
    deployed_os_config = Column(JSONEncoded, default={})
    deployed_package_config = Column(JSONEncoded, default={})
    config_validated = Column(Boolean, default=False)
    adapter_id = Column(Integer, ForeignKey('adapter.id'))
    adapter_name = Column(String(80), nullable=True)
    creator_id = Column(Integer, ForeignKey('user.id'))
    clusterhosts = relationship(
        ClusterHost,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('cluster')
    )
    state = relationship(
        ClusterState,
        uselist=False,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('cluster')
    )

    def __init__(self, name, **kwargs):
        self.name = name
        self.state = ClusterState()
        super(Cluster, self).__init__(**kwargs)

    def initialize(self):
        adapter = self.adapter
        if adapter:
            self.put_package_config = {
                'roles': [role.name for role in adapter.roles]
            }

    def update(self):
        if self.reinstall_distributed_system:
            if self.state in ['SUCCESSFUL', 'ERROR']:
                if self.config_validated:
                    self.state.state = 'INITIALIZED'
                else:
                    self.state.state = 'UNINITIALIZED'
                self.state.update()
        os = self.os
        if os:
            self.os_name = os.name
        else:
            self.os_name = None
            self.os_config = {}
        adapter = self.adapter
        if adapter:
            self.adapter_name = adapter.name
            self.distributed_system = adapter.adapter_distributed_system
            self.distributed_system_name = self.distributed_system.name
        else:
            self.adapter_name = None
            self.distributed_system = None
            self.distributed_system_name = None
        super(Cluster, self).update()

    def validate(self):
        creator = self.creator
        if not creator:
            raise exception.InvalidParameter(
                'creator is not set in cluster %s' % self.id
            )
        os = self.os
        if os and not os.deployable:
            raise exception.InvalidParameter(
                'os %s is not deployable' % os.name
            )
        adapter = self.adapter
        if adapter:
            if not adapter.deployable:
                raise exception.InvalidParameter(
                    'adapter %s is not deployable' % adapter.name
                )
            supported_os_ids = [
                adapter_os.os.id for adapter_os in adapter.supported_oses
            ]
            if os and os.id not in supported_os_ids:
                raise exception.InvalidParameter(
                    'os %s is not supported' % os.name
                )
            distributed_system = self.distributed_system
            if distributed_system and not distributed_system.deployable:
                raise exception.InvalidParamerter(
                    'distributed system %s is not deployable' % (
                        distributed_system.name
                    )
                )
        super(Cluster, self).validate()

    @property
    def patched_os_config(self):
        return self.os_config

    @patched_os_config.setter
    def patched_os_config(self, value):
        self.os_config = util.merge_dict(dict(self.os_config), value)
        logging.info('patch cluster %s os config: %s', self.id, value)
        self.config_validated = False

    @property
    def put_os_config(self):
        return self.os_config

    @put_os_config.setter
    def put_os_config(self, value):
        os_config = dict(self.os_config)
        os_config.update(value)
        self.os_config = os_config
        logging.info('put cluster %s os config: %s', self.id, value)
        self.config_validated = False

    @property
    def patched_package_config(self):
        return self.package_config

    @patched_package_config.setter
    def patched_package_config(self, value):
        package_config = dict(self.package_config)
        self.package_config = util.merge_dict(package_config, value)
        logging.info('patch cluster %s package config: %s', self.id, value)
        self.config_validated = False

    @property
    def put_package_config(self):
        return self.package_config

    @put_package_config.setter
    def put_package_config(self, value):
        package_config = dict(self.package_config)
        package_config.update(value)
        self.package_config = package_config
        logging.info('put cluster %s package config: %s', self.id, value)
        self.config_validated = False

    @hybrid_property
    def owner(self):
        return self.creator.email

    @owner.expression
    def owner(cls):
        return cls.creator.email

    @property
    def distributed_system_installed(self):
        return self.state.state == 'SUCCESSFUL'

    def state_dict(self):
        return self.state.to_dict()

    def to_dict(self):
        dict_info = super(Cluster, self).to_dict()
        dict_info.update({
            'distributed_system_installed': self.distributed_system_installed,
            'owner': self.owner,
        })
        return dict_info


# User, Permission relation table
class UserPermission(BASE, HelperMixin, TimestampMixin):
    """User permission  table."""
    __tablename__ = 'user_permission'
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    permission_id = Column(
        Integer,
        ForeignKey('permission.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    __table_args__ = (
        UniqueConstraint('user_id', 'permission_id', name='constraint'),
    )

    def __init__(self, user_id, permission_id, **kwargs):
        self.user_id = user_id
        self.permission_id = permission_id

    @hybrid_property
    def name(self):
        return self.permission.name

    def to_dict(self):
        dict_info = self.permission.to_dict()
        dict_info.update(super(UserPermission, self).to_dict())
        return dict_info


class Permission(BASE, HelperMixin, TimestampMixin):
    """Permission table."""
    __tablename__ = 'permission'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True)
    alias = Column(String(100))
    description = Column(Text)
    user_permissions = relationship(
        UserPermission,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('permission')
    )

    def __init__(self, name, **kwargs):
        self.name = name
        super(Permission, self).__init__(**kwargs)


class UserToken(BASE, HelperMixin):
    """user token table."""
    __tablename__ = 'user_token'

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    token = Column(String(256), unique=True)
    expire_timestamp = Column(
        DateTime, default=lambda: datetime.datetime.now()
    )

    def __init__(self, token, **kwargs):
        self.token = token
        super(UserToken, self).__init__(**kwargs)

    def validate(self):
        if not self.user:
            raise exception.InvalidParameter(
                'user is not set in token: %s' % self.token
            )
        super(UserToken, self).validate()


class UserLog(BASE, HelperMixin):
    """User log table."""
    __tablename__ = 'user_log'

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    action = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now())

    @hybrid_property
    def user_email(self):
        return self.user.email

    def validate(self):
        if not self.user:
            raise exception.InvalidParameter(
                'user is not set in user log: %s' % self.id
            )
        super(UserLog, self).validate()


class User(BASE, HelperMixin, TimestampMixin):
    """User table."""
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    email = Column(String(80), unique=True)
    crypted_password = Column('password', String(225))
    firstname = Column(String(80))
    lastname = Column(String(80))
    is_admin = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    user_permissions = relationship(
        UserPermission,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('user')
    )
    user_logs = relationship(
        UserLog,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('user')
    )
    user_tokens = relationship(
        UserToken,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('user')
    )
    clusters = relationship(
        Cluster,
        backref=backref('creator')
    )
    hosts = relationship(
        Host,
        backref=backref('creator')
    )

    def __init__(self, email, **kwargs):
        self.email = email
        super(User, self).__init__(**kwargs)

    def validate(self):
        if not self.crypted_password:
            raise exception.InvalidParameter(
                'password is not set in user : %s' % self.email
            )
        super(User, self).validate()

    @property
    def password(self):
        return '***********'

    @password.setter
    def password(self, password):
        self.crypted_password = util.encrypt(password)

    @hybrid_property
    def permissions(self):
        permissions = []
        for user_permission in self.user_permissions:
            permissions.append(user_permission.permission)

        return permissions

    def to_dict(self):
        dict_info = super(User, self).to_dict()
        dict_info['permissions'] = [
            permission.to_dict()
            for permission in self.permissions
        ]
        return dict_info

    def __str__(self):
        return '%s[email:%s,is_admin:%s,active:%s]' % (
            self.__class__.__name__,
            self.email, self.is_admin, self.active
        )


class SwitchMachine(BASE, HelperMixin, TimestampMixin):
    """Switch Machine table."""
    __tablename__ = 'switch_machine'
    id = Column(
        Integer, primary_key=True
    )
    switch_id = Column(
        Integer,
        ForeignKey('switch.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    machine_id = Column(
        Integer,
        ForeignKey('machine.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    port = Column(String(80), nullable=True)
    vlans = Column(JSONEncoded, default=[])
    __table_args__ = (
        UniqueConstraint('switch_id', 'machine_id', name='constraint'),
    )

    def __init__(self, switch_id, machine_id, **kwargs):
        self.switch_id = switch_id
        self.machine_id = machine_id
        super(SwitchMachine, self).__init__(**kwargs)

    def validate(self):
        if not self.switch:
            raise exception.InvalidParameter(
                'switch is not set in %s' % self.id
            )
        if not self.machine:
            raise exception.Invalidparameter(
                'machine is not set in %s' % self.id
            )
        if not self.port:
            raise exception.InvalidParameter(
                'port is not set in %s' % self.id
            )

    @hybrid_property
    def mac(self):
        return self.machine.mac

    @hybrid_property
    def tag(self):
        return self.machine.tag

    @property
    def switch_ip(self):
        return self.switch.ip

    @hybrid_property
    def switch_ip_int(self):
        return self.switch.ip_int

    @switch_ip_int.expression
    def switch_ip_int(cls):
        return Switch.ip_int

    @hybrid_property
    def switch_vendor(self):
        return self.switch.vendor

    @switch_vendor.expression
    def switch_vendor(cls):
        return Switch.vendor

    @property
    def patched_vlans(self):
        return self.vlans

    @patched_vlans.setter
    def patched_vlans(self, value):
        if not value:
            return
        vlans = list(self.vlans)
        for item in value:
            if item not in vlans:
                vlans.append(item)
        self.vlans = vlans

    def to_dict(self):
        dict_info = self.machine.to_dict()
        dict_info.update(super(SwitchMachine, self).to_dict())
        dict_info['switch_ip'] = self.switch.ip
        return dict_info


class Machine(BASE, HelperMixin, TimestampMixin):
    """Machine table."""
    __tablename__ = 'machine'
    id = Column(Integer, primary_key=True)
    mac = Column(String(24), unique=True)
    ipmi_credentials = Column(JSONEncoded, default={})
    tag = Column(JSONEncoded, default={})
    location = Column(JSONEncoded, default={})

    switch_machines = relationship(
        SwitchMachine,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('machine')
    )
    host = relationship(
        Host,
        uselist=False,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('machine')
    )

    def __init__(self, mac, **kwargs):
        self.mac = mac
        super(Machine, self).__init__(**kwargs)

    def validate(self):
        try:
            netaddr.EUI(self.mac)
        except Exception:
            raise exception.InvalidParameter(
                'mac address %s format uncorrect' % self.mac
            )
        super(Machine, self).validate()

    @property
    def patched_ipmi_credentials(self):
        return self.ipmi_credentials

    @patched_ipmi_credentials.setter
    def patched_ipmi_credentials(self, value):
        self.ipmi_credentials = (
            util.merge_dict(dict(self.ipmi_credentials), value)
        )

    @property
    def patched_tag(self):
        return self.tag

    @patched_tag.setter
    def patched_tag(self, value):
        tag = dict(self.tag)
        tag.update(value)
        self.tag = value

    @property
    def patched_location(self):
        return self.location

    @patched_location.setter
    def patched_location(self, value):
        location = dict(self.location)
        location.update(value)
        self.location = location

    def to_dict(self):
        dict_info = {}
        dict_info['switches'] = [
            {
                'switch_ip': switch_machine.switch_ip,
                'port': switch_machine.port,
                'vlans': switch_machine.vlans
            }
            for switch_machine in self.switch_machines
        ]
        if dict_info['switches']:
            dict_info.update(dict_info['switches'][0])
        dict_info.update(super(Machine, self).to_dict())
        return dict_info


class Switch(BASE, HelperMixin, TimestampMixin):
    """Switch table."""
    __tablename__ = 'switch'
    id = Column(Integer, primary_key=True)
    ip_int = Column('ip', BigInteger, unique=True)
    credentials = Column(JSONEncoded, default={})
    vendor = Column(String(256), nullable=True)
    state = Column(Enum('initialized', 'unreachable', 'notsupported',
                        'repolling', 'error', 'under_monitoring',
                        name='switch_state'),
                   ColumnDefault('initialized'))
    filters = Column(JSONEncoded, default=[])
    switch_machines = relationship(
        SwitchMachine,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('switch')
    )

    def __init__(self, ip_int, **kwargs):
        self.ip_int = ip_int
        super(Switch, self).__init__(**kwargs)

    @property
    def ip(self):
        return str(netaddr.IPAddress(self.ip_int))

    @ip.setter
    def ip(self, ipaddr):
        self.ip_int = int(netaddr.IPAddress(ipaddr))

    @property
    def patched_credentials(self):
        return self.credentials

    @patched_credentials.setter
    def patched_credentials(self, value):
        self.credentials = util.merge_dict(dict(self.credentials), value)

    @property
    def patched_filters(self):
        return self.filters

    @patched_filters.setter
    def patched_filters(self, value):
        if not value:
            return
        filters = list(self.filters)
        for item in value:
            found_filter = False
            for switch_filter in filters:
                if switch_filter['filter_name'] == item['filter_name']:
                    switch_filter.update(item)
                    found_filter = True
                    break
            if not found_filter:
                filters.append(item)
        self.filters = filters

    def to_dict(self):
        dict_info = super(Switch, self).to_dict()
        dict_info['ip'] = self.ip
        return dict_info


class OSConfigMetadata(BASE, MetadataMixin):
    """OS config metadata."""
    __tablename__ = "os_config_metadata"

    id = Column(Integer, primary_key=True)
    os_id = Column(
        Integer,
        ForeignKey(
            'os.id', onupdate='CASCADE', ondelete='CASCADE'
        )
    )
    parent_id = Column(
        Integer,
        ForeignKey(
            'os_config_metadata.id', onupdate='CASCADE', ondelete='CASCADE'
        )
    )
    field_id = Column(
        Integer,
        ForeignKey(
            'os_config_field.id', onupdate='CASCADE', ondelete='CASCADE'
        )
    )
    children = relationship(
        'OSConfigMetadata',
        passive_deletes=True, passive_updates=True,
        backref=backref('parent', remote_side=id)
    )
    __table_args__ = (
        UniqueConstraint('path', 'os_id', name='constraint'),
    )

    def __init__(self, path, **kwargs):
        self.path = path
        super(OSConfigMetadata, self).__init__(**kwargs)

    def validate(self):
        if not self.os:
            raise exception.InvalidParameter(
                'os is not set in os metadata %s' % self.id
            )
        super(OSConfigMetadata, self).validate()


class OSConfigField(BASE, FieldMixin):
    """OS config fields."""
    __tablename__ = 'os_config_field'

    metadatas = relationship(
        OSConfigMetadata,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('field'))

    def __init__(self, field, **kwargs):
        self.field = field
        super(OSConfigField, self).__init__(**kwargs)


class AdapterOS(BASE, HelperMixin):
    """Adapter OS table."""
    __tablename__ = 'adapter_os'

    id = Column(Integer, primary_key=True)
    os_id = Column(
        Integer,
        ForeignKey(
            'os.id',
            onupdate='CASCADE', ondelete='CASCADE'
        )
    )
    adapter_id = Column(
        Integer,
        ForeignKey(
            'adapter.id',
            onupdate='CASCADE', ondelete='CASCADE'
        )
    )

    def __init__(self, os_id, adapter_id, **kwargs):
        self.os_id = os_id
        self.adapter_id = adapter_id
        super(AdapterOS, self).__init__(**kwargs)

    def to_dict(self):
        dict_info = self.os.to_dict()
        dict_info.update(super(AdapterOS, self).to_dict())
        return dict_info


class OperatingSystem(BASE, HelperMixin):
    """OS table."""
    __tablename__ = 'os'

    id = Column(Integer, primary_key=True)
    parent_id = Column(
        Integer,
        ForeignKey('os.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=True
    )
    name = Column(String(80), unique=True)
    deployable = Column(Boolean, default=False)

    metadatas = relationship(
        OSConfigMetadata,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('os')
    )
    clusters = relationship(
        Cluster,
        backref=backref('os')
    )
    hosts = relationship(
        Host,
        backref=backref('os')
    )
    children = relationship(
        'OperatingSystem',
        passive_deletes=True, passive_updates=True,
        backref=backref('parent', remote_side=id)
    )
    supported_adapters = relationship(
        AdapterOS,
        passive_deletes=True, passive_updates=True,
        backref=backref('os')
    )

    def __init__(self, name):
        self.name = name
        super(OperatingSystem, self).__init__()

    @property
    def root_metadatas(self):
        return [
            metadata for metadata in self.metadatas
            if metadata.parent_id is None
        ]

    def metadata_dict(self):
        dict_info = {}
        if self.parent:
            dict_info.update(self.parent.metadata_dict())
        for metadata in self.root_metadatas:
            dict_info.update(metadata.to_dict())
        return dict_info


class AdapterRole(BASE, HelperMixin):
    """Adapter's roles."""

    __tablename__ = "adapter_role"
    id = Column(Integer, primary_key=True)
    name = Column(String(80))
    display_name = Column(String(80))
    description = Column(Text)
    optional = Column(Boolean)
    adapter_id = Column(
        Integer,
        ForeignKey(
            'adapter.id',
            onupdate='CASCADE',
            ondelete='CASCADE'
        )
    )

    __table_args__ = (
        UniqueConstraint('name', 'adapter_id', name='constraint'),
    )

    def __init__(self, name, adapter_id, **kwargs):
        self.name = name
        self.adapter_id = adapter_id
        super(AdapterRole, self).__init__(**kwargs)

    def initialize(self):
        if not self.description:
            self.description = self.name
        if not self.display_name:
            self.display_name = self.name


class PackageConfigMetadata(BASE, MetadataMixin):
    """package config metadata."""
    __tablename__ = "package_config_metadata"

    id = Column(Integer, primary_key=True)
    adapter_id = Column(
        Integer,
        ForeignKey(
            'adapter.id',
            onupdate='CASCADE', ondelete='CASCADE'
        )
    )
    parent_id = Column(
        Integer,
        ForeignKey(
            'package_config_metadata.id',
            onupdate='CASCADE', ondelete='CASCADE'
        )
    )
    field_id = Column(
        Integer,
        ForeignKey(
            'package_config_field.id',
            onupdate='CASCADE', ondelete='CASCADE'
        )
    )
    children = relationship(
        'PackageConfigMetadata',
        passive_deletes=True, passive_updates=True,
        backref=backref('parent', remote_side=id)
    )

    __table_args__ = (
        UniqueConstraint('path', 'adapter_id', name='constraint'),
    )

    def __init__(
        self, path, **kwargs
    ):
        self.path = path
        super(PackageConfigMetadata, self).__init__(**kwargs)

    def validate(self):
        if not self.adapter:
            raise exception.InvalidParameter(
                'adapter is not set in package metadata %s' % self.id
            )
        super(PackageConfigMetadata, self).validate()


class PackageConfigField(BASE, FieldMixin):
    """Adapter cofig metadata fields."""
    __tablename__ = "package_config_field"

    metadatas = relationship(
        PackageConfigMetadata,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('field'))

    def __init__(self, field, **kwargs):
        self.field = field
        super(PackageConfigField, self).__init__(**kwargs)


class Adapter(BASE, HelperMixin):
    """Adapter table."""
    __tablename__ = 'adapter'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True)
    display_name = Column(String(80))
    parent_id = Column(
        Integer,
        ForeignKey(
            'adapter.id',
            onupdate='CASCADE', ondelete='CASCADE'
        ),
        nullable=True
    )
    distributed_system_id = Column(
        Integer,
        ForeignKey(
            'distributed_system.id',
            onupdate='CASCADE', ondelete='CASCADE'
        ),
        nullable=True
    )
    os_installer_id = Column(
        Integer,
        ForeignKey(
            'os_installer.id',
            onupdate='CASCADE', ondelete='CASCADE'
        ),
        nullable=True
    )
    package_installer_id = Column(
        Integer,
        ForeignKey(
            'package_installer.id',
            onupdate='CASCADE', ondelete='CASCADE'
        ),
        nullable=True
    )
    deployable = Column(
        Boolean, default=False
    )

    supported_oses = relationship(
        AdapterOS,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('adapter')
    )

    roles = relationship(
        AdapterRole,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('adapter')
    )
    children = relationship(
        'Adapter',
        passive_deletes=True, passive_updates=True,
        backref=backref('parent', remote_side=id)
    )
    metadatas = relationship(
        PackageConfigMetadata,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('adapter')
    )
    clusters = relationship(
        Cluster,
        backref=backref('adapter')
    )

    __table_args__ = (
        UniqueConstraint(
            'distributed_system_id',
            'os_installer_id', 'package_installer_id', name='constraint'
        ),
    )

    def __init__(
        self, name, **kwargs
    ):
        self.name = name
        super(Adapter, self).__init__(**kwargs)

    def initialize(self):
        if not self.display_name:
            self.display_name = self.name

    @property
    def root_metadatas(self):
        return [
            metadata for metadata in self.metadatas
            if metadata.parent_id is None
        ]

    def metadata_dict(self):
        dict_info = {}
        if self.parent:
            dict_info.update(self.parent.metadata_dict())
        for metadata in self.root_metadatas:
            dict_info.update(metadata.to_dict())
        return dict_info

    @property
    def adapter_package_installer(self):
        if self.package_installer:
            return self.package_installer
        elif self.parent:
            return self.parent.adapter_package_installer
        else:
            return None

    @property
    def adapter_os_installer(self):
        if self.os_installer:
            return self.os_installer
        elif self.parent:
            return self.parent.adapter_os_installer
        else:
            return None

    @property
    def adapter_distributed_system(self):
        distributed_system = self.distributed_system
        if distributed_system:
            return distributed_system
        parent = self.parent
        if parent:
            return parent.adapter_distributed_system
        else:
            return None

    @property
    def adapter_supported_oses(self):
        supported_oses = self.supported_oses
        if supported_oses:
            return supported_oses
        parent = self.parent
        if parent:
            return parent.adapter_supported_oses
        else:
            return []

    @property
    def adapter_roles(self):
        roles = self.roles
        if roles:
            return roles
        parent = self.parent
        if parent:
            return parent.adapter_roles
        else:
            return []

    def to_dict(self):
        dict_info = super(Adapter, self).to_dict()
        dict_info.update({
            'roles': [
                role.to_dict() for role in self.adapter_roles
            ],
            'supported_oses': [
                adapter_os.to_dict()
                for adapter_os in self.adapter_supported_oses
            ],
        })
        distributed_system = self.distributed_system
        if distributed_system:
            dict_info['distributed_system_name'] = distributed_system.name
        os_installer = self.adapter_os_installer
        if os_installer:
            dict_info['os_installer'] = os_installer.to_dict()
        package_installer = self.adapter_package_installer
        if package_installer:
            dict_info['package_installer'] = package_installer.to_dict()
        return dict_info


class DistributedSystem(BASE, HelperMixin):
    """distributed system table."""
    __tablename__ = 'distributed_system'

    id = Column(Integer, primary_key=True)
    parent_id = Column(
        Integer,
        ForeignKey(
            'distributed_system.id',
            onupdate='CASCADE', ondelete='CASCADE'
        ),
        nullable=True
    )
    name = Column(String(80), unique=True)
    deployable = Column(String(80), default=False)

    adapters = relationship(
        Adapter,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('distributed_system')
    )
    clusters = relationship(
        Cluster,
        backref=backref('distributed_system')
    )
    children = relationship(
        'DistributedSystem',
        passive_deletes=True, passive_updates=True,
        backref=backref('parent', remote_side=id)
    )

    def __init__(self, name):
        self.name = name
        super(DistributedSystem, self).__init__()


class OSInstaller(BASE, InstallerMixin):
    """OS installer table."""
    __tablename__ = 'os_installer'
    id = Column(Integer, primary_key=True)
    adpaters = relationship(
        Adapter,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('os_installer')
    )

    def __init__(self, instance_name, **kwargs):
        self.instance_name = instance_name
        super(OSInstaller, self).__init__(**kwargs)


class PackageInstaller(BASE, InstallerMixin):
    """package installer table."""
    __tablename__ = 'package_installer'
    id = Column(Integer, primary_key=True)
    adapters = relationship(
        Adapter,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('package_installer')
    )

    def __init__(self, instance_name, **kwargs):
        self.instance_name = instance_name
        super(PackageInstaller, self).__init__(**kwargs)


class Network(BASE, TimestampMixin, HelperMixin):
    """network table."""
    __tablename__ = 'network'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True)
    subnet = Column(String(80), unique=True)

    host_networks = relationship(
        HostNetwork,
        passive_deletes=True, passive_updates=True,
        cascade='all, delete-orphan',
        backref=backref('network')
    )

    def __init__(self, subnet, **kwargs):
        self.subnet = subnet
        super(Network, self).__init__(**kwargs)

    def initialize(self):
        if not self.name:
            self.name = self.subnet
        super(Network, self).initialize()

    def validate(self):
        try:
            netaddr.IPNetwork(self.subnet)
        except Exception:
            raise exception.InvalidParameter(
                'subnet %s format is uncorrect' % self.subnet
            )


class LogProgressingHistory(BASE):
    """host installing log history for each file.

    :param id: int, identity as primary key.
    :param pathname: str, the full path of the installing log file. unique.
    :param position: int, the position of the log file it has processed.
    :param partial_line: str, partial line of the log.
    :param progressing: float, indicate the installing progress between 0 to 1.
    :param message: str, str, the installing message.
    :param severity: Enum, the installing message severity.
                     ('ERROR', 'WARNING', 'INFO')
    :param line_matcher_name: str, the line matcher name of the log processor.
    :param update_timestamp: datetime, the latest timestamp the entry updated.
    """
    __tablename__ = 'log_progressing_history'
    id = Column(Integer, primary_key=True)
    pathname = Column(String(80), unique=True)
    position = Column(Integer, ColumnDefault(0))
    partial_line = Column(Text)
    percentage = Column(Float, ColumnDefault(0.0))
    message = Column(Text)
    severity = Column(Enum('ERROR', 'WARNING', 'INFO'), ColumnDefault('INFO'))
    line_matcher_name = Column(String(80), ColumnDefault('start'))
    update_timestamp = Column(DateTime, default=datetime.datetime.now(),
                              onupdate=datetime.datetime.now())

    def __init__(self, **kwargs):
        super(LogProgressingHistory, self).__init__(**kwargs)

    def __repr__(self):
        return (
            'LogProgressingHistory[%r: position %r,'
            'partial_line %r,percentage %r,message %r,'
            'severity %r]'
        ) % (
            self.pathname, self.position,
            self.partial_line,
            self.percentage,
            self.message,
            self.severity
        )