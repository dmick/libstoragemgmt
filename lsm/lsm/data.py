# Copyright (C) 2011-2013 Red Hat, Inc.
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Author: tasleson

from abc import ABCMeta, abstractmethod
import json
from json.decoder import WHITESPACE
import datetime
from common import get_class, sh, LsmError, ErrorNumber, default_property


def txt_a(txt, append):
    if len(txt):
        return txt + ',' + append
    else:
        return append


def get_key(dictionary, value):
    keys = [k for k, v in dictionary.items() if v == value]
    if len(keys) > 0:
        return keys[0]
    return None


class DataEncoder(json.JSONEncoder):
    """
    Custom json encoder for objects derived form ILsmData
    """

    def default(self, my_class):
        if not isinstance(my_class, IData):
            raise ValueError('incorrect class type:' + str(type(my_class)))
        else:
            return my_class.to_dict()


class DataDecoder(json.JSONDecoder):
    """
    Custom json decoder for objects derived from ILsmData
    """

    @staticmethod
    def __process_dict(d):
        """
        Processes a dictionary
        """
        rc = {}

        if 'class' in d:
            rc = IData.factory(d)
        else:
            for (k, v) in d.iteritems():
                rc[k] = DataDecoder.__decode(v)

        return rc

    @staticmethod
    def __process_list(l):
        """
        Processes a list
        """
        rc = []
        for elem, value in enumerate(l):
            if type(value) is list:
                rc.append(DataDecoder.__process_list(value))
            elif type(value) is dict:
                rc.append(DataDecoder.__process_dict(value))
            else:
                rc.append(value)
        return rc

    @staticmethod
    def __decode(e):
        """
        Decodes the parsed json
        """
        if type(e) is dict:
            return DataDecoder.__process_dict(e)
        elif type(e) is list:
            return DataDecoder.__process_list(e)
        else:
            return e

    def decode(self, json_string, _w=WHITESPACE.match):
        decoded = json.loads(json_string)
        decoded = DataDecoder.__decode(decoded)
        return decoded


class IData(object):
    """
    Base class functionality of serializable
    classes.
    """
    __metaclass__ = ABCMeta

    def to_dict(self):
        """
        Represent the class as a dictionary
        """
        rc = {'class': self.__class__.__name__}

        #If one of the attributes is another IData we will
        #process that too, is there a better way to handle this?
        for (k, v) in self.__dict__.items():
            if isinstance(v, IData):
                rc[k[1:]] = v.to_dict()
            else:
                rc[k[1:]] = v

        return rc

    @staticmethod
    def factory(d):
        """
        Factory for creating the appropriate class given a dictionary.
        This only works for objects that inherit from IData
        """
        if 'class' in d:
            class_name = d['class']
            del d['class']
            c = get_class(__name__ + '.' + class_name)

            #If any of the parameters are themselves an IData process them
            for k, v in d.items():
                if isinstance(v, dict) and 'class' in v:
                    d['_' + k] = IData.factory(d.pop(k))
                else:
                    d['_' + k] = d.pop(k)

            i = c(**d)
            return i

    def __str__(self):
        """
        Used for human string representation.
        """
        return str(self.to_dict())

    @abstractmethod
    def column_headers(self):
        pass

    @abstractmethod
    def column_data(self, human=False, enum_as_number=False):
        pass

# Status, using DMTF 2.23.0Final CIM_ManagedSystemElement['OperationalStatus']
    MAX_STATUS_BITS = 64
    STATUS_UNKNOWN = 1 << 0
    STATUS_OTHER = 1 << 1
    STATUS_OK = 1 << 2
    STATUS_DEGRADED = 1 << 3
    STATUS_STRESSED = 1 << 4
    STATUS_PREDICTIVE_FAILURE = 1 << 5
    STATUS_ERROR = 1 << 6
    STATUS_NON_RECOVERABLE_ERROR = 1 << 7
    STATUS_STARTING = 1 << 8
    STATUS_STOPPING = 1 << 9
    STATUS_STOPPED = 1 << 10
    STATUS_IN_SERVICE = 1 << 11
    STATUS_NO_CONTACT = 1 << 12
    STATUS_LOST_COMMUNICATION = 1 << 13
    STATUS_ABORTED = 1 << 14
    STATUS_DORMANT = 1 << 15
    STATUS_SUPPORTING_ENTITY_IN_ERROR = 1 << 16
    STATUS_COMPLETED = 1 << 17
    STATUS_POWER_MODE = 1 << 18

    STATUS = {
        STATUS_UNKNOWN:                 'UNKNOWN',
        STATUS_OTHER:                   'OTHER',
        STATUS_OK:                      'OK',
        STATUS_DEGRADED:                'DEGRADED',
        STATUS_STRESSED:                'STRESSED',
        STATUS_PREDICTIVE_FAILURE:      'PREDICTIVE_FAILURE',
        STATUS_ERROR:                   'ERROR',
        STATUS_NON_RECOVERABLE_ERROR:   'NON_RECOVERABLE_ERROR',
        STATUS_STARTING:                'STARTING',
        STATUS_STOPPING:                'STOPPING',
        STATUS_STOPPED:                 'STOPPED',
        STATUS_IN_SERVICE:              'IN_SERVICE',
        STATUS_NO_CONTACT:              'NO_CONTACT',
        STATUS_LOST_COMMUNICATION:      'LOST_COMMUNICATION',
        STATUS_ABORTED:                 'ABORTED',
        STATUS_DORMANT:                 'DORMANT',
        STATUS_SUPPORTING_ENTITY_IN_ERROR: 'SUPPORTING_ENTITY_IN_ERROR',
        STATUS_COMPLETED:               'COMPLETED',
        STATUS_POWER_MODE:              'POWER_MODE',
    }

    @staticmethod
    def status_to_str(status):
        """
        Convert Tier status to a string
        When having multiple status, will use a comma between them
        """
        status_str = ''
        for x in IData.STATUS.keys():
            if x & status:
                status_str = txt_a(status_str, IData.STATUS[x])
        if status_str:
            return status_str
        return IData.STATUS[IData.STATUS_UNKNOWN]

    @staticmethod
    def status_dmtf_to_lsm_type(dmtf_status):
        """
        In DMTF, OperationalStatus is a list of number.
        In libstoragemgmt, it's a number using binary bit.
        """
        rt = 0
        try:
            for x in dmtf_status:
                if 1 <= x < IData.MAX_STATUS_BITS:
                    rt |= (1 << x)
            return rt
        except (TypeError, ValueError):
            return IData.STATUS_UNKNOWN

    # Enable status, using SNIA SMI-S 1.4 rev6 and DMTF CIM 2.23.0Final:
    #   CIM_EnabledLogicalElement['EnabledState']
    #   CIM_DiskDrive['EnabledState']
    #   CIM_LogicalPort['EnabledState']
    ENABLE_STATUS_UNKNOWN = 0
    ENABLE_STATUS_OTHER = 1
    ENABLE_STATUS_ENABLED = 2
    # Enabled (2) indicates that the element is or could be executing
    # commands, will process any queued commands, and queues new requests.
    ENABLE_STATUS_DISABLED = 3
    # Enabled (2) indicates that the element is or could be executing
    # commands, will process any queued commands, and queues new requests.
    ENABLE_STATUS_SHUTTING_DOWN = 4
    # Shutting Down (4) indicates that the element is in the process of going
    # to a Disabled state.
    ENABLE_STATUS_NOT_APPLICABLE = 5
    # Not Applicable (5) indicates the element does not support being enabled
    # or disabled.
    ENABLE_STATUS_ENABLED_BUT_OFFLINE = 6
    # Enabled but Offline (6) indicates that the element might be completing
    # commands, and will drop any new requests.
    ENABLE_STATUS_IN_TEST = 7
    # Test (7) indicates that the element is in a test state.
    ENABLE_STATUS_DEFERRED = 8
    # Deferred (8) indicates that the element might be completing commands,
    # but will queue any new requests.
    ENABLE_STATUS_QUIESCE = 9
    # Quiesce (9) indicates that the element is enabled but in a restricted
    # mode.
    ENABLE_STATUS_STARTING = 10
    # Starting (10) indicates that the element is in the process of going to
    # an Enabled state. New requests are queued.

    ENABLE_STATUS = {
        ENABLE_STATUS_UNKNOWN:              'UNKNOWN',
        ENABLE_STATUS_OTHER:                'OTHER',
        ENABLE_STATUS_ENABLED:              'ENABLED',
        ENABLE_STATUS_DISABLED:             'DISABLED',
        ENABLE_STATUS_SHUTTING_DOWN:        'SHUTTING_DOWN',
        ENABLE_STATUS_NOT_APPLICABLE:       'NOT_APPLICABLE',
        ENABLE_STATUS_ENABLED_BUT_OFFLINE:  'ENABLE_BUT_OFFLINE',
        ENABLE_STATUS_IN_TEST:              'IN_TEST',
        ENABLE_STATUS_DEFERRED:             'DEFERRED',
        ENABLE_STATUS_QUIESCE:              'QUIESCE',
        ENABLE_STATUS_STARTING:             'STARTING',
    }

    @staticmethod
    def enable_status_to_str(enable_status):
        if enable_status in IData.ENABLE_STATUS.keys():
            return IData.ENABLE_STATUS[enable_status]
        return IData.ENABLE_STATUS[IData.ENABLE_STATUS_UNKNOWN]

    @staticmethod
    def enable_status_str_to_type(enable_status_str):
        key = get_key(IData.ENABLE_STATUS, enable_status_str)
        if key or key == 0:
            return key
        return IData.ENABLE_STATUS_UNKNOWN

    # We use '-1' to indicate we failed to get the requested number.
    # For example, when block found is undetectable, we use '-1' instead of
    # confusing 0.
    BLOCK_COUNT_NOT_FOUND = -1
    BLOCK_SIZE_NOT_FOUND = -1


@default_property('id', doc="Unique identifier")
@default_property('type', doc="Enumerated initiator type")
@default_property('name', doc="User supplied name")
class Initiator(IData):
    """
    Represents an initiator.
    """
    (TYPE_OTHER, TYPE_PORT_WWN, TYPE_NODE_WWN, TYPE_HOSTNAME, TYPE_ISCSI,
     TYPE_SAS) = (1, 2, 3, 4, 5, 7)

    type_map = {1: 'Other', 2: 'Port WWN', 3: 'Node WWN', 4: 'Hostname',
                5: 'iSCSI', 7: "SAS"}

    def _type_to_str(self, init_type):
        return Initiator.type_map[init_type]

    def __init__(self, _id, _type, _name):

        if not _name or not len(_name):
            name = "Unsupported"

        self._id = _id            # Identifier
        self._type = _type        # Initiator type id
        self._name = _name        # Initiator name

    def column_headers(self):
        return [['ID', 'Name', 'Type']]

    def column_data(self, human=False, enum_as_number=False):
        if enum_as_number:
            return [[self.id, self.name, self.type]]
        else:
            return [[self.id, self.name, self._type_to_str(self.type)]]


@default_property('id', doc="Unique identifier")
@default_property('name', doc="Disk name (aka. vendor)")
@default_property('disk_type', doc="Enumerated type of disk")
@default_property('block_size', doc="Size of each block")
@default_property('num_of_blocks', doc="Total number of blocks")
@default_property('status', doc="Enumerated status")
@default_property('health', doc="Enumerated system health")
@default_property('system_id', doc="System identifier")
@default_property("optional_params", doc="Optional data")
class Disk(IData):
    """
    Represents a disk.
    """
    # Disk Health status, using DMTF 2.29.0 CIM_DiskDrive
    #   CIM_DiskDrive['HealthState']
    #   aka. CIM_ManagedSystemElement['HealthState']
    HEALTH_UNKNOWN = 0
    #   The implementation cannot report on HealthState at this time.
    HEALTH_OK = 5
    #   The element is fully functional and is operating within normal
    #   operational parameters and without error.
    HEALTH_DEGRADED = 10
    #   The element is in working order and all functionality is
    #   provided. However, the element is not working to the best of its
    #   abilities. For example, the element might not be operating at
    #   optimal performance or it might be reporting recoverable errors.
    HEALTH_MINOR_FAIL = 15
    #   All functionality is available but some might be degraded.
    HEALTH_MAJOR_FAIL = 20
    #   The element is failing. It is possible that some or all of the
    #   functionality of this component is degraded or not working.
    HEALTH_CRITICAL_FAIL = 25
    #   The element is non-functional and recovery might not be possible.
    HEALTH_NON_RECOVERABLE_ERR = 30
    #   The element has completely failed, and recovery is not possible.
    #   All functionality provided by this element has been lost.

    HEALTH = {
        HEALTH_UNKNOWN:             'UNKNOWN',
        HEALTH_OK:                  'OK',
        HEALTH_DEGRADED:            'DEGRADED',
        HEALTH_MINOR_FAIL:          'MINOR_FAIL',
        HEALTH_MAJOR_FAIL:          'MAJOR_FAIL',
        HEALTH_CRITICAL_FAIL:       'CRITICAL_FAIL',
        HEALTH_NON_RECOVERABLE_ERR: 'NON_RECOVERABLE_ERR',
    }

    # Disk Type, using DMTF 2.31.0+ CIM_DiskDrive['InterconnectType']
    DISK_TYPE_UNKNOWN = 0
    DISK_TYPE_OTHER = 1
    DISK_TYPE_NOT_APPLICABLE = 2
    DISK_TYPE_ATA = 3     # IDE disk is seldomly used.
    DISK_TYPE_SATA = 4
    DISK_TYPE_SAS = 5
    DISK_TYPE_FC = 6
    DISK_TYPE_SOP = 7     # SCSI over PCIe, often holding SSD

    # Due to complesity of disk types, we are defining these beside DMTF
    # standards:
    DISK_TYPE_NL_SAS = 51    # Near-Line SAS==SATA disk + SAS port.

    # in DMTF CIM 2.34.0+ CIM_DiskDrive['DiskType'], they also defined
    # SSD and HYBRID disk type. We use it as faillback.
    DISK_TYPE_HDD = 52    # Normal HDD
    DISK_TYPE_SSD = 53    # Solid State Drive
    DISK_TYPE_HYBRID = 54    # uses a combination of HDD and SSD

    DISK_TYPE = {
        DISK_TYPE_UNKNOWN:          'UNKNOWN',
        DISK_TYPE_OTHER:            'OTHER',
        DISK_TYPE_NOT_APPLICABLE:   'NOT_APPLICABLE',
        DISK_TYPE_ATA:              'ATA',
        DISK_TYPE_SATA:             'SATA',
        DISK_TYPE_SAS:              'SAS',
        DISK_TYPE_FC:               'FC',
        DISK_TYPE_SOP:              'SOP',
        DISK_TYPE_NL_SAS:           'NL_SAS',
        DISK_TYPE_HDD:              'HDD',
        DISK_TYPE_SSD:              'SSD',
        DISK_TYPE_HYBRID:           'HYBRID',
    }

    # DMTF Disk Type
    DMTF_DISK_TYPE_UNKNOWN = 0
    DMTF_DISK_TYPE_OTHER = 1
    DMTF_DISK_TYPE_HDD = 2
    DMTF_DISK_TYPE_SSD = 3
    DMTF_DISK_TYPE_HYBRID = 4

    DMTF_DISK_TYPE = {
        DMTF_DISK_TYPE_UNKNOWN: 'UNKNOWN',
        DMTF_DISK_TYPE_OTHER:   'OTHER',
        DMTF_DISK_TYPE_HDD:     'HDD',
        DMTF_DISK_TYPE_SSD:     'SSD',
        DMTF_DISK_TYPE_HYBRID:  'HYBRID',
    }

    @staticmethod
    def dmtf_disk_type_2_lsm_disk_type(dmtf_disk_type):
        if dmtf_disk_type in Disk.DMTF_DISK_TYPE.keys():
            return Disk.disk_type_str_to_type(
                Disk.DMTF_DISK_TYPE[dmtf_disk_type])
        else:
            return Disk.DISK_TYPE_UNKNOWN

    MEDIUM_ERROR_COUNT_NOT_SUPPORT = -1
    PREDICTIVE_FAILURE_COUNT_NOT_SUPPORT = -1

    OPT_PROPERTIES_2_HEADER = {
        'sn':                       'SN',
        'part_num':                 'Part Number',
        'vendor':                   'Vendor',
        'model':                    'Model',
        'enable_status':            'Enable Status',
        'media_err_count':          'Media Error Count',
        'predictive_fail_count':    'Predictive Fail Count',
        'error_info':               'Error Info',
        'owner_ctrler_id':          'Controller Owner',
    }

    def __init__(self, _id, _name, _disk_type, _block_size, _num_of_blocks,
                 _status, _health, _system_id, _optional_params=None):
        self._id = _id
        self._name = _name
        self._disk_type = _disk_type
        self._block_size = _block_size
        self._num_of_blocks = _num_of_blocks
        self._status = _status
        self._health = _health
        self._system_id = _system_id

        if _optional_params is None:
            self._optional_params = Properties()
        else:
            #Make sure the properties only contain ones we permit
            allowed = set(Disk.OPT_PROPERTIES_2_HEADER.keys())
            actual = set(_optional_params.list())

            if actual <= allowed:
                self._optional_params = _optional_params
            else:
                raise LsmError(ErrorNumber.INVALID_ARGUMENT,
                               "Property keys are invalid: %s" %
                               "".join(actual - allowed))

    @property
    def size_bytes(self):
        """
        Disk size in bytes.
        """
        return self.block_size * self.num_of_blocks

    @staticmethod
    def health_to_str(health):
        if health in Disk.HEALTH.keys():
            return Disk.HEALTH[health]
        return Disk.HEALTH[Disk.HEALTH_UNKNOWN]

    @staticmethod
    def health_str_to_type(health_str):
        key = get_key(Disk.HEALTH, health_str)
        if key or key == 0:
            return key
        return Disk.HEALTH_UNKNOWN

    @staticmethod
    def disk_type_to_str(disk_type):
        if disk_type in Disk.DISK_TYPE.keys():
            return Disk.DISK_TYPE[disk_type]
        return Disk.DISK_TYPE[Disk.DISK_TYPE_UNKNOWN]

    @staticmethod
    def disk_type_str_to_type(disk_type_str):
        key = get_key(Disk.DISK_TYPE, disk_type_str)
        if key or key == 0:
            return key
        return Disk.DISK_TYPE_UNKNOWN

    def __str__(self):
        return self.name

    def _opt_column_headers(self):
        opt_headers = []
        opt_pros = self.optional_params.list()
        for opt_pro in opt_pros:
            opt_headers.extend([Disk.OPT_PROPERTIES_2_HEADER[opt_pro]])
        return opt_headers

    def column_headers(self):
        headers = ['ID', 'Name', 'Disk Type', 'Block Size', '#blocks', 'Size',
                   'Status', 'Health', 'System ID']
        opt_headers = self._opt_column_headers()
        if opt_headers:
            headers.extend(opt_headers)
        return [headers]

    def _opt_column_data(self, human=False, enum_as_number=False):
        opt_data_values = []
        opt_pros = self.optional_params.list()
        for opt_pro in opt_pros:
            opt_pro_value = self.optional_params.get(opt_pro)
            if enum_as_number:
                # current no size convert needed.
                pass
            else:
                if opt_pro == 'enable_status':
                    opt_pro_value = Disk.enable_status_to_str(opt_pro_value)

            opt_data_values.extend([opt_pro_value])
        return opt_data_values

    def column_data(self, human=False, enum_as_number=False):
        data_values = []
        if enum_as_number:
            data_values = [
                self.id, self.name, self.disk_type,
                sh(self.block_size, human), self.num_of_blocks,
                sh(self.size_bytes, human), self.status, self.health,
                self.system_id
            ]
        else:
            data_values = [
                self.id, self.name, Disk.disk_type_to_str(self.disk_type),
                sh(self.block_size, human), self.num_of_blocks,
                sh(self.size_bytes, human), Disk.status_to_str(self.status),
                Disk.health_to_str(self.health), self.system_id
            ]
        opt_data_values = self._opt_column_data(human, enum_as_number)
        if opt_data_values:
            data_values.extend(opt_data_values)
        return [data_values]


@default_property('id', doc="Unique identifier")
@default_property('name', doc="User given name")
@default_property('vpd83', doc="Vital product page 0x83 identifier")
@default_property('block_size', doc="Volume block size")
@default_property('num_of_blocks', doc="Number of blocks")
@default_property('status', doc="Enumerated volume status")
@default_property('system_id', "System identifier")
@default_property('pool_id', "Pool identifier")
class Volume(IData):
    """
    Represents a volume.
    """

    # Volume status Note: Volumes can have multiple status bits set at same
    # time.
    (STATUS_UNKNOWN, STATUS_OK, STATUS_DEGRADED, STATUS_ERR, STATUS_STARTING,
     STATUS_DORMANT) = (0x0, 0x1, 0x2, 0x4, 0x8, 0x10)

    #Replication types
    (REPLICATE_UNKNOWN, REPLICATE_SNAPSHOT, REPLICATE_CLONE, REPLICATE_COPY,
     REPLICATE_MIRROR_SYNC, REPLICATE_MIRROR_ASYNC) = \
        (-1, 1, 2, 3, 4, 5)

    #Provisioning types
    (PROVISION_UNKNOWN, PROVISION_THIN, PROVISION_FULL, PROVISION_DEFAULT) = \
        (-1, 1, 2, 3)

    @staticmethod
    def prov_string_to_type(prov_type):
        if prov_type == 'DEFAULT':
            return Volume.PROVISION_DEFAULT
        elif prov_type == "FULL":
            return Volume.PROVISION_FULL
        elif prov_type == "THIN":
            return Volume.PROVISION_THIN
        else:
            return Volume.PROVISION_UNKNOWN

    @staticmethod
    def rep_String_to_type(rt):
        if rt == "SNAPSHOT":
            return Volume.REPLICATE_SNAPSHOT
        elif rt == "CLONE":
            return Volume.REPLICATE_CLONE
        elif rt == "COPY":
            return Volume.REPLICATE_COPY
        elif rt == "MIRROR_SYNC":
            return Volume.REPLICATE_MIRROR_SYNC
        elif rt == "MIRROR_ASYNC":
            return Volume.REPLICATE_MIRROR_ASYNC
        else:
            return Volume.REPLICATE_UNKNOWN

    #Initiator access
    (ACCESS_READ_ONLY, ACCESS_READ_WRITE, ACCESS_NONE) = (1, 2, 3)

    @staticmethod
    def status_to_str(status):
        if status == 1:
            return "OK"
        elif status == 0:
            return "Unknown"
        else:
            rc = ""
            if status & Volume.STATUS_OK:
                rc = txt_a(rc, "OK")
            if status & Volume.STATUS_DEGRADED:
                rc = txt_a(rc, "Degraded")
            if status & Volume.STATUS_DORMANT:
                rc = txt_a(rc, "Dormant")
            if status & Volume.STATUS_ERR:
                rc = txt_a(rc, "Error")
            if status & Volume.STATUS_STARTING:
                rc = txt_a(rc, "Starting")
            return rc

    @staticmethod
    def access_string_to_type(access):
        if access == "RW":
            return Volume.ACCESS_READ_WRITE
        else:
            return Volume.ACCESS_READ_ONLY

    def __init__(self, _id, _name, _vpd83, _block_size, _num_of_blocks,
                 _status, _system_id, _pool_id):
        self._id = _id                        # Identifier
        self._name = _name                    # Human recognisable name
        self._vpd83 = _vpd83                  # SCSI page 83 unique ID
        self._block_size = _block_size        # Block size
        self._num_of_blocks = _num_of_blocks  # Number of blocks
        self._status = _status                # Status
        self._system_id = _system_id          # System id this volume belongs
        self._pool_id = _pool_id              # Pool id this volume belongs

    @property
    def size_bytes(self):
        """
        Volume size in bytes.
        """
        return self.block_size * self.num_of_blocks

    def __str__(self):
        return self.name

    def column_headers(self):
        return [['ID', 'Name', 'vpd83', 'bs', '#blocks', 'status', 'size',
                 'System ID', 'Pool ID']]

    def column_data(self, human=False, enum_as_number=False):
        if enum_as_number:
            return [[self.id, self.name, self.vpd83, self.block_size,
                     self.num_of_blocks,
                     self.status, sh(self.size_bytes, human), self.system_id,
                     self.pool_id]]
        else:
            return [[self.id, self.name, self.vpd83, self.block_size,
                     self.num_of_blocks,
                     self.status_to_str(self.status),
                     sh(self.size_bytes, human), self.system_id, self.pool_id]]


@default_property('id', doc="Unique identifier")
@default_property('name', doc="User defined system name")
@default_property('status', doc="Enumerated status of system")
class System(IData):
    (STATUS_UNKNOWN, STATUS_OK, STATUS_DEGRADED, STATUS_ERROR,
     STATUS_PREDICTIVE_FAILURE, STATUS_VENDOR_SPECIFIC) = \
        (0x0, 0x1, 0x2, 0x4, 0x8, 0x10)

    @staticmethod
    def status_to_str(status):
        if status == 0:
            return "Unknown"
        elif status == 1:
            return "OK"
        else:
            rc = ""
            if status & System.STATUS_OK:
                rc = txt_a(rc, "OK")
            if status & System.STATUS_DEGRADED:
                rc = txt_a(rc, "Degraded")
            if status & System.STATUS_ERROR:
                rc = txt_a(rc, "Error")
            if status & System.STATUS_PREDICTIVE_FAILURE:
                rc = txt_a(rc, "Predictive failure")
            if status & System.STATUS_VENDOR_SPECIFIC:
                rc = txt_a(rc, "Vendor specific status")

            return rc

    def __init__(self, _id, _name, _status):
        self._id = _id        # For SMI-S this is the CIM_ComputerSystem->Name
        self._name = _name        # For SMI-S , CIM_ComputerSystem->ElementName
        self._status = _status    # OperationalStatus

    def column_headers(self):
        return [['ID', 'Name', 'Status']]

    def column_data(self, human=False, enum_as_number=False):
        if enum_as_number:
            return [[self.id, self.name, self.status]]
        else:
            return [[self.id, self.name, self.status_to_str(self.status)]]


@default_property('id', doc="Unique identifier")
@default_property('name', doc="User supplied name")
@default_property('total_space', doc="Total space in bytes")
@default_property('free_space', doc="Free space in bytes")
@default_property('system_id', doc="System identifier")
class Pool(IData):
    """
    Pool specific information
    """

    def __init__(self, _id, _name, _total_space, _free_space, _system_id):
        self._id = _id                    # Identifier
        self._name = _name                # Human recognisable name
        self._total_space = _total_space  # Total size
        self._free_space = _free_space    # Free space available
        self._system_id = _system_id      # Systemd id this pool belongs

    def column_headers(self):
        return [['ID', 'Name', 'Total space', 'Free space', 'System ID']]

    def column_data(self, human=False, enum_as_number=False):
        return [[self.id, self.name, sh(self.total_space, human),
                 sh(self.free_space, human), self.system_id]]


@default_property('id', doc="Unique identifier")
@default_property('name', doc="File system name")
@default_property('total_space', doc="Total space in bytes")
@default_property('free_space', doc="Free space available")
@default_property('pool_id', doc="What pool the file system resides on")
@default_property('system_id', doc="System ID")
class FileSystem(IData):
    def __init__(self, _id, _name, _total_space, _free_space, _pool_id,
                 _system_id):
        self._id = _id
        self._name = _name
        self._total_space = _total_space
        self._free_space = _free_space
        self._pool_id = _pool_id
        self._system_id = _system_id

    def column_headers(self):
        return [['ID', 'Name', 'Total space', 'Free space', 'Pool ID']]

    def column_data(self, human=False, enum_as_number=False):
        return [[self.id, self.name, sh(self.total_space, human),
                 sh(self.free_space, human), self.pool_id]]


@default_property('id', doc="Unique identifier")
@default_property('name', doc="Snapshot name")
@default_property('ts', doc="Time stamp the snapshot was created")
class Snapshot(IData):
    def __init__(self, _id, _name, _ts):
        self._id = _id
        self._name = _name
        self._ts = int(_ts)

    def column_headers(self):
        return [['ID', 'Name', 'Created']]

    def column_data(self, human=False, enum_as_number=False):
        return [[self.id, self.name, datetime.datetime.fromtimestamp(self.ts)]]


@default_property('id', doc="Unique identifier")
@default_property('fs_id', doc="Filesystem that is exported")
@default_property('export_path', doc="Export path")
@default_property('auth', doc="Authentication type")
@default_property('root', doc="List of hosts with no_root_squash")
@default_property('rw', doc="List of hosts with Read & Write privileges")
@default_property('ro', doc="List of hosts with Read only privileges")
@default_property('anonuid', doc="UID for anonymous user id")
@default_property('anongid', doc="GID for anonymous group id")
@default_property('options', doc="String containing advanced options")
class NfsExport(IData):
    ANON_UID_GID_NA = -1
    ANON_UID_GID_ERROR = (ANON_UID_GID_NA - 1)

    def __init__(self, _id, _fs_id, _export_path, _auth, _root, _rw, _ro,
                 _anonuid, _anongid, _options):
        assert (_fs_id is not None)
        assert (_export_path is not None)

        self._id = _id
        self._fs_id = _fs_id          # File system exported
        self._export_path = _export_path     # Export path
        self._auth = _auth            # Authentication type
        self._root = _root            # List of hosts with no_root_squash
        self._rw = _rw                # List of hosts with read/write
        self._ro = _ro                # List of hosts with read/only
        self._anonuid = _anonuid      # uid for anonymous user id
        self._anongid = _anongid      # gid for anonymous group id
        self._options = _options      # NFS options

    def column_headers(self):
        return [["Key", 'Value']]

    def column_data(self, human=False, enum_as_number=False):
        return [
            ['ID', self.id],
            ['File system ID', self.fs_id],
            ['Export Path', self.export_path],
            ['Authentication', self.auth],
            ['Root', self.root],
            ['Read/Write', self.rw],
            ['ReadOnly', self.ro],
            ['Anon UID', self.anonuid],
            ['Anon GID', self.anongid],
            ['Options', self.options]
        ]


@default_property('src_block', doc="Source logical block address")
@default_property('dest_block', doc="Destination logical block address")
@default_property('block_count', doc="Number of blocks")
class BlockRange(IData):
    def __init__(self, _src_block, _dest_block, _block_count):
        self._src_block = _src_block
        self._dest_block = _dest_block
        self._block_count = _block_count

    def column_headers(self):
        raise NotImplementedError

    def column_data(self, human=False, enum_as_number=False):
        raise NotImplementedError


@default_property('id', doc="Unique instance identifier")
@default_property('name', doc="Access group name")
@default_property('initiators', doc="List of initiators")
@default_property('system_id', doc="System identifier")
class AccessGroup(IData):
    def __init__(self, _id, _name, _initiators, _system_id='NA'):
        self._id = _id
        self._name = _name                # AccessGroup name
        self._initiators = _initiators    # List of initiators
        self._system_id = _system_id      # System id this group belongs

    def column_headers(self):
        return [['ID', 'Name', 'Initiator ID', 'System ID']]

    def column_data(self, human=False, enum_as_number=False):
        rc = []

        if len(self.initiators):
            for i in self.initiators:
                rc.append([self.id, self.name, i, self.system_id])
        else:
            rc.append([self.id, self.name, 'No initiators', self.system_id])
        return rc


class Properties(IData):
    def column_data(self, human=False, enum_as_number=False):
        return [sorted(self._values.iterkeys(),
                       key=lambda k: self._values[k][1])]

    def column_headers(self):
        return [sorted(self._values.keys())]

    def __init__(self, _values=None):
        if _values is not None:
            self._values = _values
        else:
            self._values = {}

    def list(self):
        rc = self._values.keys()
        return rc

    def get(self, key):
        return self._values[key]

    def set(self, key, value):
        self._values[key] = value


class Capabilities(IData):
    (
        UNSUPPORTED,        # Not supported
        SUPPORTED,          # Supported
        SUPPORTED_OFFLINE,  # Supported, but only when item is in offline state
        NOT_IMPLEMENTED,    # Not implemented
        UNKNOWN             # Capability not known
    ) = (0, 1, 2, 3, 4)

    _NUM = 512

    #Array wide
    BLOCK_SUPPORT = 0       # Array handles block operations
    FS_SUPPORT = 1          # Array handles file system

    #Block operations
    VOLUMES = 20
    VOLUME_CREATE = 21
    VOLUME_RESIZE = 22

    VOLUME_REPLICATE = 23
    VOLUME_REPLICATE_CLONE = 24
    VOLUME_REPLICATE_COPY = 25
    VOLUME_REPLICATE_MIRROR_ASYNC = 26
    VOLUME_REPLICATE_MIRROR_SYNC = 27

    VOLUME_COPY_RANGE_BLOCK_SIZE = 28
    VOLUME_COPY_RANGE = 29
    VOLUME_COPY_RANGE_CLONE = 30
    VOLUME_COPY_RANGE_COPY = 31

    VOLUME_DELETE = 33

    VOLUME_ONLINE = 34
    VOLUME_OFFLINE = 35

    ACCESS_GROUP_GRANT = 36
    ACCESS_GROUP_REVOKE = 37
    ACCESS_GROUP_LIST = 38
    ACCESS_GROUP_CREATE = 39
    ACCESS_GROUP_DELETE = 40
    ACCESS_GROUP_ADD_INITIATOR = 41
    ACCESS_GROUP_DEL_INITIATOR = 42

    VOLUMES_ACCESSIBLE_BY_ACCESS_GROUP = 43
    ACCESS_GROUPS_GRANTED_TO_VOLUME = 44

    VOLUME_CHILD_DEPENDENCY = 45
    VOLUME_CHILD_DEPENDENCY_RM = 46

    INITIATORS = 47
    INITIATORS_GRANTED_TO_VOLUME = 48

    VOLUME_INITIATOR_GRANT = 50
    VOLUME_INITIATOR_REVOKE = 51
    VOLUME_ACCESSIBLE_BY_INITIATOR = 52
    VOLUME_ISCSI_CHAP_AUTHENTICATION = 53

    VOLUME_THIN = 55

    #File system
    FS = 100
    FS_DELETE = 101
    FS_RESIZE = 102
    FS_CREATE = 103
    FS_CLONE = 104
    FILE_CLONE = 105
    FS_SNAPSHOTS = 106
    FS_SNAPSHOT_CREATE = 107
    FS_SNAPSHOT_CREATE_SPECIFIC_FILES = 108
    FS_SNAPSHOT_DELETE = 109
    FS_SNAPSHOT_REVERT = 110
    FS_SNAPSHOT_REVERT_SPECIFIC_FILES = 111
    FS_CHILD_DEPENDENCY = 112
    FS_CHILD_DEPENDENCY_RM = 113
    FS_CHILD_DEPENDENCY_RM_SPECIFIC_FILES = 114

    #NFS
    EXPORT_AUTH = 120
    EXPORTS = 121
    EXPORT_FS = 122
    EXPORT_REMOVE = 123
    EXPORT_CUSTOM_PATH = 124

    def to_dict(self):
        rc = {'class': self.__class__.__name__,
              'cap': ''.join(['%02x' % b for b in self._cap])}
        return rc

    def __init__(self, _cap=None):
        if _cap is not None:
            self._cap = bytearray(_cap.decode('hex'))
        else:
            self._cap = bytearray(Capabilities._NUM)

    def get(self, capability):
        if capability > len(self._cap):
            return Capabilities.UNKNOWN
        return self._cap[capability]

    def set(self, capability, value=SUPPORTED):
        self._cap[capability] = value
        return None

    def enable_all(self):
        for i in range(len(self._cap)):
            self._cap[i] = Capabilities.SUPPORTED

    def column_headers(self):
        raise NotImplementedError

    def column_data(self, human=False, enum_as_number=False):
        raise NotImplementedError


if __name__ == '__main__':
    #TODO Need some unit tests that encode/decode all the types with nested
    pass
