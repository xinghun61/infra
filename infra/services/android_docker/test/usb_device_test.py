# Copyright (c) 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
import docker
import mock
import subprocess
import unittest
import usb1

from infra.services.android_docker import usb_device

from battor import battor_error
from devil.utils import battor_device_mapping


class FakeUSBContext(object):
  def __init__(self, devices):
    self.devices = devices

  def getDeviceList(self, **kwargs):  # pylint: disable=unused-argument
    for d in self.devices:
      yield d


class FakeLibusbDevice(object):
  """Mocks a libusb1.USBDevice.

  usb_device.Device wraps it. Mocked here to verify wrapper class
  behaves correctly.
  """
  def __init__(self, serial=None, port=1, bus=2, dev=3, product=4,
               settings=None, port_list=None):
    self.port = port
    self.bus = bus
    self.dev = dev
    self.product = product
    self.settings = settings
    self.serial = serial
    self.port_list = port_list or [1,2,3]

  def getPortNumber(self):
    return self.port

  def getBusNumber(self):
    return self.bus

  def getDeviceAddress(self):
    return self.dev

  def getProductID(self):
    return self.product

  def getSerialNumber(self):
    if self.serial is None:
      raise usb1.USBError('omg no serial')
    return self.serial

  def getPortNumberList(self):
    if self.port_list is None:
      raise usb1.USBError('omg no port list')
    return self.port_list

  def iterSettings(self):
    for i in self.settings or []:
      yield i


class FakeDeviceSetting(object):
  def __init__(self, classs, subclass, protocol):
    self.classs = classs
    self.subclass = subclass
    self.protocol = protocol

  def getClass(self):
    return self.classs

  def getSubClass(self):
    return self.subclass

  def getProtocol(self):
    return self.protocol


class TestDevice(unittest.TestCase):
  def setUp(self):
    self.supported_interface = usb_device._SUPPORTED_INTERFACES[0]
    self.supported_setting = FakeDeviceSetting(*self.supported_interface)
    self.libusb_device = FakeLibusbDevice(
        serial='serial1', settings=[self.supported_setting])

  @mock.patch('os.stat')
  @mock.patch('os.major')
  @mock.patch('os.minor')
  def test_dev_file_stat(self, mock_minor, mock_major, _):
    mock_major.return_value = 123
    mock_minor.return_value = 987
    device = usb_device.USBDevice(self.libusb_device)
    self.assertEquals(str(device), 'serial1')
    self.assertEquals(device.minor, 987)
    self.assertEquals(device.major, 123)

  def test_dev_faulty_serial(self):
    self.libusb_device.serial = None
    device = usb_device.USBDevice(self.libusb_device)
    self.assertEquals(device.serial, None)

  def test_dev_faulty_port_list(self):
    self.libusb_device.port_list = None
    device = usb_device.USBDevice(self.libusb_device)
    self.assertEquals(device.port_list, None)

  def test_get_port_list(self):
    self.libusb_device.port_list = [1, 2, 3]
    device = usb_device.USBDevice(self.libusb_device)
    self.assertEquals(device.port_list, [1, 2, 3])
    self.assertEquals(device.port_list, [1, 2, 3])


class TestBattorTTYDevice(unittest.TestCase):
  def setUp(self):
    self.tty_path = '/dev/ttyBattor'
    self.serial = 'battor_serial'

  @mock.patch('os.stat')
  @mock.patch('os.major')
  @mock.patch('os.minor')
  def test_dev_file_stat(self, mock_minor, mock_major, _):
    mock_major.return_value = 123
    mock_minor.return_value = 987
    battor = usb_device.BattorTTYDevice(self.tty_path, self.serial)
    self.assertEquals(battor.minor, 987)
    self.assertEquals(battor.major, 123)

  @mock.patch('os.stat')
  def test_dev_file_stat_error(self, mock_stat):
    mock_stat.side_effect = OSError('omg error')
    battor = usb_device.BattorTTYDevice(self.tty_path, self.serial)
    self.assertEquals(battor.minor, None)
    self.assertEquals(battor.major, None)

  @mock.patch('subprocess.check_output')
  def test_get_syspath(self, mock_subprocess):
    udevadm_output = """
    P: /devices/pci0000:00/0000:00:1c.7/0000:08:00.0/usb3/3-1/3-1.4/3-1.4.4/3-1.4.4:1.0/ttyUSB1/tty/ttyUSB1
    N: ttyUSB1
    S: serial/by-id/usb-Mellow_Research_LLC_BattOr_v3.3_MABA-AABL-if00-port0
    S: serial/by-path/pci-0000:08:00.0-usb-0:1.4.4:1.0-port0
    E: DEVNAME=/dev/ttyUSB1
    E: DEVPATH=/devices/pci0000:00/0000:00:1c.7/0000:08:00.0/usb3/3-1/3-1.4/3-1.4.4/3-1.4.4:1.0/ttyUSB1/tty/ttyUSB1
    E: ID_BUS=usb
    E: ID_MODEL=BattOr_v3.3
    E: ID_MODEL_ENC=BattOr\x20v3.3
    E: ID_MODEL_FROM_DATABASE=FT232 USB-Serial (UART) IC
    E: ID_MODEL_ID=6001
    E: ID_PATH=pci-0000:08:00.0-usb-0:1.4.4:1.0
    E: ID_PATH_TAG=pci-0000_08_00_0-usb-0_1_4_4_1_0
    E: ID_REVISION=0600
    E: ID_SERIAL=Mellow_Research_LLC_BattOr_v3.3_MABA-AABL
    E: ID_SERIAL_SHORT=MABA-AABL
    E: ID_TYPE=generic
    E: SUBSYSTEM=tty
    E: USEC_INITIALIZED=247076153791
    """
    mock_subprocess.return_value = udevadm_output
    battor = usb_device.BattorTTYDevice(self.tty_path, self.serial)
    syspath = battor.syspath
    self.assertEquals(
        syspath,
        '/devices/pci0000:00/0000:00:1c.7/0000:08:00.0/usb3/3-1/3-1.4/3-1.4.4/'
        '3-1.4.4:1.0/ttyUSB1/tty/ttyUSB1')
    mock_subprocess.assert_called_with(
        ['/sbin/udevadm', 'info', battor.tty_path])
    # Fetch the path again to test caching.
    syspath = battor.syspath
    self.assertEquals(
        syspath,
        '/devices/pci0000:00/0000:00:1c.7/0000:08:00.0/usb3/3-1/3-1.4/3-1.4.4/'
        '3-1.4.4:1.0/ttyUSB1/tty/ttyUSB1')

  @mock.patch('subprocess.check_output')
  def test_get_syspath_no_output(self, mock_subprocess):
    udevadm_output = """
    blah blah blah
    bla bla
    blahhhhh
    """
    mock_subprocess.return_value = udevadm_output
    battor = usb_device.BattorTTYDevice(self.tty_path, self.serial)
    syspath = battor.syspath
    self.assertEquals(syspath, None)

  @mock.patch('subprocess.check_output')
  def test_get_syspath_error(self, mock_subprocess):
    mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'omg error')
    battor = usb_device.BattorTTYDevice(self.tty_path, self.serial)
    syspath = battor.syspath
    self.assertEquals(syspath, None)


class TestGetDevices(TestDevice):
  def setUp(self):
    super(TestGetDevices, self).setUp()
    self.wrong_interface_device = FakeLibusbDevice(settings=[])
    self.no_serial_device = FakeLibusbDevice(
        settings=[self.supported_setting])
    self.libusb_device_long_port_list = FakeLibusbDevice(
        serial='seriallllll', settings=[self.supported_setting])
    self.libusb_device_long_port_list.port_list.append(1)

    self.all_devices = [
        self.libusb_device,
        self.libusb_device_long_port_list,
        self.wrong_interface_device,
        self.no_serial_device,
    ]

    self.usb_context = FakeUSBContext(self.all_devices)

  @mock.patch('usb1.USBContext')
  def test_get_android_devices(self, mock_usb_context):
    mock_usb_context.return_value = self.usb_context
    devices = usb_device.get_android_devices(None)
    self.assertEquals(len(devices), 2)
    self.assertEquals(devices[0].serial, self.libusb_device.serial)
    self.assertEquals(
        devices[1].serial, self.libusb_device_long_port_list.serial)

  @mock.patch('usb1.USBContext')
  def test_no_android_devices(self, mock_usb_context):
    self.usb_context = FakeUSBContext([])
    mock_usb_context.return_value = self.usb_context
    devices = usb_device.get_android_devices(None)
    self.assertEquals(len(devices), 0)

  @mock.patch('os.stat')
  @mock.patch('usb1.USBContext')
  def test_get_android_devices_os_error(self, mock_usb_context, mock_os_stat):
    self.usb_context = FakeUSBContext([self.libusb_device])
    mock_usb_context.return_value = self.usb_context
    mock_os_stat.side_effect = OSError('omg can\'t stat')
    devices = usb_device.get_android_devices(None)
    self.assertEquals(len(devices), 1)
    self.assertEquals(devices[0].serial, self.libusb_device.serial)
    self.assertEquals(devices[0].major, None)
    self.assertEquals(devices[0].minor, None)

  @mock.patch('usb1.USBContext')
  def test_filter_devices(self, mock_usb_context):
    d1 = self.libusb_device
    d2 = copy.copy(self.libusb_device)
    d2.serial = 'serial2'
    d3 = copy.copy(self.libusb_device_long_port_list)
    d3.serial = 'serial3'
    self.usb_context = FakeUSBContext([d1, d2, d3])
    mock_usb_context.return_value = self.usb_context
    devices = usb_device.get_android_devices(['serial2', 'serial3'])
    self.assertEquals(len(devices), 2)
    self.assertEquals(devices[0].serial, 'serial2')
    self.assertEquals(devices[1].serial, 'serial3')

  @mock.patch('usb1.USBContext')
  def test_get_devices_repeated_serials(self, mock_usb_context):
    d1_copy1 = self.libusb_device
    d1_copy2 = copy.copy(self.libusb_device)
    d1_copy3 = copy.copy(self.libusb_device)
    d2 = copy.copy(self.libusb_device)
    d2.serial = 'serial2'
    d3 = copy.copy(self.libusb_device)
    d3.serial = 'serial3'
    self.usb_context = FakeUSBContext([d1_copy1, d1_copy2, d1_copy3, d2, d3])
    mock_usb_context.return_value = self.usb_context
    devices = usb_device.get_android_devices(None)
    self.assertEquals(len(devices), 2)
    self.assertEquals(devices[0].serial, 'serial2')
    self.assertEquals(devices[1].serial, 'serial3')

  @mock.patch('devil.utils.battor_device_mapping.GetBattOrPathFromPhoneSerial')
  @mock.patch('devil.utils.battor_device_mapping.GenerateSerialMap')
  @mock.patch('usb1.USBContext')
  def test_get_devices_with_battors(self, mock_usb_context, mock_generate_map,
                                    mock_get_battor_path):
    d1 = self.libusb_device
    d1.serial = 'serial1'
    d2 = copy.copy(self.libusb_device)
    d2.serial = 'serial2'
    self.usb_context = FakeUSBContext([d1, d2])
    mock_usb_context.return_value = self.usb_context
    mock_generate_map.return_value = {
        'serial1': 'battorSerial1', 'serial2': 'battorSerial2'}
    def map_battor_serial_to_tty(device_serial, **kwargs):  # pragma: no cover
      # pylint: disable=unused-argument
      if device_serial == 'serial1':
        return '/dev/ttyBattor1'
      elif device_serial == 'serial2':
        return '/dev/ttyBattor2'
      raise Exception('Unexpected device serial: %s', device_serial)
    mock_get_battor_path.side_effect = map_battor_serial_to_tty
    devices = usb_device.get_android_devices(None)

    self.assertEquals(devices[0].serial, 'serial1')
    self.assertEquals(devices[0].battor.serial, 'battorSerial1')
    self.assertEquals(devices[0].battor.tty_path, '/dev/ttyBattor1')
    self.assertEquals(devices[1].serial, 'serial2')
    self.assertEquals(devices[1].battor.serial, 'battorSerial2')
    self.assertEquals(devices[1].battor.tty_path, '/dev/ttyBattor2')

  @mock.patch('devil.utils.battor_device_mapping.GenerateSerialMap')
  @mock.patch('usb1.USBContext')
  def test_get_devices_with_no_battors(self, mock_usb_context,
                                       mock_generate_map):
    d1 = self.libusb_device
    d1.serial = 'serial1'
    d2 = copy.copy(self.libusb_device)
    d2.serial = 'serial2'
    self.usb_context = FakeUSBContext([d1, d2])
    mock_usb_context.return_value = self.usb_context
    mock_generate_map.side_effect = battor_error.BattOrError('omg no battor')
    devices = usb_device.get_android_devices(None)

    self.assertEquals(devices[0].serial, 'serial1')
    self.assertEquals(devices[0].battor, None)
    self.assertEquals(devices[1].serial, 'serial2')
    self.assertEquals(devices[1].battor, None)


class TestGetPhysicalPorts(TestDevice):
  def setUp(self):
    super(TestGetPhysicalPorts, self).setUp()
    self.libusb_devices = []
    self.port_mappings = {}
    for i in xrange(1, 8):
      libusb_device = FakeLibusbDevice(
          serial='serial%d' % i, settings=[self.supported_setting])
      self.port_mappings[i] = 'serial%d' % i
      self.libusb_devices.append(libusb_device)

  @mock.patch('devil.utils.find_usb_devices.GetAllPhysicalPortToSerialMaps')
  def test_known_hub(self, mock_physical_ports):
    mock_physical_ports.return_value = [self.port_mappings]
    devices = [usb_device.USBDevice(d) for d in self.libusb_devices]
    usb_device.assign_physical_ports(devices)

    self.assertEquals(devices[0].physical_port, 1)
    self.assertEquals(devices[1].physical_port, 2)
    self.assertEquals(devices[2].physical_port, 3)
    self.assertEquals(devices[3].physical_port, 4)
    self.assertEquals(devices[4].physical_port, 5)
    self.assertEquals(devices[5].physical_port, 6)
    self.assertEquals(devices[6].physical_port, 7)

  @mock.patch('devil.utils.find_usb_devices.GetAllPhysicalPortToSerialMaps')
  def test_many_unknown_hubs(self, mock_physical_ports):
    mock_physical_ports.return_value = [{}, {}, {}]
    devices = [usb_device.USBDevice(d) for d in self.libusb_devices]
    usb_device.assign_physical_ports(devices)
    for d in devices:
      self.assertEquals(d.physical_port, None)
