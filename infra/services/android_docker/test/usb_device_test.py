# Copyright (c) 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
import docker
import mock
import unittest
import usb1

from infra.services.android_docker import usb_device


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


class TestGetPhysicalPorts(TestDevice):
  def setUp(self):
    super(TestGetPhysicalPorts, self).setUp()
    self.libusb_devices = []
    for i in xrange(1, 8):
      libusb_device = FakeLibusbDevice(
          serial='serial%d' % i, settings=[self.supported_setting])
      self.libusb_devices.append(libusb_device)

    self.libusb_devices[0].port_list = [1, 2, 1]
    self.libusb_devices[1].port_list = [1, 2, 2]
    self.libusb_devices[2].port_list = [1, 2, 3]
    self.libusb_devices[3].port_list = [1, 2, 4, 1]
    self.libusb_devices[4].port_list = [1, 2, 4, 2]
    self.libusb_devices[5].port_list = [1, 2, 4, 3]
    self.libusb_devices[6].port_list = [1, 2, 4, 4]

  def test_full_hub(self):
    devices = [usb_device.USBDevice(d) for d in self.libusb_devices]

    usb_device.assign_physical_ports(devices)

    self.assertEquals(devices[0].physical_port, 1)
    self.assertEquals(devices[1].physical_port, 2)
    self.assertEquals(devices[2].physical_port, 3)
    self.assertEquals(devices[3].physical_port, 4)
    self.assertEquals(devices[4].physical_port, 5)
    self.assertEquals(devices[5].physical_port, 6)
    self.assertEquals(devices[6].physical_port, 7)

  def test_incomplete_hub_list_1(self):
    # Skip the 5th device and make sure the physical ports stay the same.
    devices = []
    for i in range(0, 4) + range(5, 7):
      devices.append(usb_device.USBDevice(self.libusb_devices[i]))

    usb_device.assign_physical_ports(devices)

    self.assertEquals(devices[0].physical_port, 1)
    self.assertEquals(devices[1].physical_port, 2)
    self.assertEquals(devices[2].physical_port, 3)
    self.assertEquals(devices[3].physical_port, 4)
    self.assertEquals(devices[4].physical_port, 6)
    self.assertEquals(devices[5].physical_port, 7)

  def test_incomplete_hub_list_2(self):
    # Skip all but the first 2 devices.
    devices = []
    for i in range(0, 2):
      devices.append(usb_device.USBDevice(self.libusb_devices[i]))

    usb_device.assign_physical_ports(devices)
    for d in devices:
      self.assertEquals(d.physical_port, None)

  def test_unexpected_hub_list(self):
    # Give the 7th device a crazy port list.
    self.libusb_devices[6].port_list = [1, 2, 4, 4, 1]
    devices = [usb_device.USBDevice(d) for d in self.libusb_devices]

    usb_device.assign_physical_ports(devices)
    for d in devices:
      self.assertEquals(d.physical_port, None)

  def test_duplicate_physical_ports(self):
    # Give the 1st and 2nd devices the same port list.
    self.libusb_devices[0].port_list = [1, 2, 1]
    self.libusb_devices[1].port_list = [1, 2, 1]
    devices = [usb_device.USBDevice(d) for d in self.libusb_devices]

    usb_device.assign_physical_ports(devices)
    for d in devices:
      self.assertEquals(d.physical_port, None)
