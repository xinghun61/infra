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
               vendor=None, settings=None, port_list=None):
    self.port = port
    self.bus = bus
    self.dev = dev
    self.product = product
    self.vendor = vendor
    self.settings = settings
    self.serial = serial
    self.port_list = port_list

  def getPortNumber(self):
    return self.port

  def getBusNumber(self):
    return self.bus

  def getDeviceAddress(self):
    return self.dev

  def getProductID(self):
    return self.product

  def getVendorID(self):
    return self.vendor

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
    self.supported_vendor = usb_device._SUPPORTED_VENDORS[0]
    self.supported_interface = usb_device._SUPPORTED_INTERFACES[0]
    self.supported_setting = FakeDeviceSetting(*self.supported_interface)
    self.libusb_device = FakeLibusbDevice(
        serial='serial1', vendor=int(self.supported_vendor, 16),
        settings=[self.supported_setting])

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
    self.wrong_vendor_device = FakeLibusbDevice(vendor=int('deadbeef', 16))
    self.wrong_interface_device = FakeLibusbDevice(
        vendor=int(self.supported_vendor, 16), settings=[])
    self.no_serial_device = FakeLibusbDevice(
        vendor=int(self.supported_vendor, 16),
        settings=[self.supported_setting])

    self.all_devices = [
        self.libusb_device,
        self.wrong_vendor_device,
        self.wrong_interface_device,
        self.no_serial_device,
    ]

    self.usb_context = FakeUSBContext(self.all_devices)

  @mock.patch('usb1.USBContext')
  def test_get_android_devices(self, mock_usb_context):
    mock_usb_context.return_value = self.usb_context
    devices = usb_device.get_android_devices(None) 
    self.assertEquals(len(devices), 1)
    self.assertEquals(devices[0].serial, 'serial1')

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
    d3 = copy.copy(self.libusb_device)
    d3.serial = 'serial3'
    self.usb_context = FakeUSBContext([d1, d2, d3])
    mock_usb_context.return_value = self.usb_context
    devices = usb_device.get_android_devices(['serial2'])
    self.assertEquals(len(devices), 1)
    self.assertEquals(devices[0].serial, 'serial2')
