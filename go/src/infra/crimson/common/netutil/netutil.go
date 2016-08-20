// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package netutil

import (
	"encoding/hex"
	"fmt"
	"net"
)

// IPStringToHexString converts an IP address into a hex string suitable for MySQL.
func IPStringToHexString(ip string) (string, error) {
	ipb := net.ParseIP(ip)
	if ipb == nil {
		return "", fmt.Errorf("parsing of IP address failed: %s", ip)
	}
	if ipb.DefaultMask() != nil {
		ipb = ipb.To4()
	}
	return "0x" + hex.EncodeToString(ipb), nil
}

// MacAddrStringToHexString turns a mac address into a hex string.
func MacAddrStringToHexString(macAddr string) (string, error) {
	mac, err := net.ParseMAC(macAddr)
	if err != nil {
		return "", err
	}
	return "0x" + hex.EncodeToString(mac), nil
}

// HexStringToHardwareAddr turns an hex string into a hardware address.
func HexStringToHardwareAddr(hexMac string) (net.HardwareAddr, error) {
	// 6 bytes in hex + leading '0x'
	if len(hexMac) < 14 {
		err := fmt.Errorf("parsing of hex string failed (too short: %d characters)",
			len(hexMac))
		return net.HardwareAddr{}, err
	}
	if hexMac[:2] != "0x" {
		return net.HardwareAddr{}, fmt.Errorf("parsing of hex string failed: %s", hexMac)
	}
	hwAddrRaw, err := hex.DecodeString(hexMac[2:])
	if err != nil {
		return net.HardwareAddr{}, err
	}
	hwAddr := make(net.HardwareAddr, len(hwAddrRaw))
	for n := 0; n < len(hwAddrRaw); n++ {
		hwAddr[n] = hwAddrRaw[n]
	}
	return hwAddr, nil
}

// HexStringToIP converts an hex string returned by MySQL into a net.IP structure.
func HexStringToIP(hexIP string) (net.IP, error) {
	// TODO(pgervais): Add decent error checking. Ex: check hexIP starts with '0x'.
	ip, err := hex.DecodeString(hexIP[2:])
	if err != nil {
		return net.IP{}, err
	}
	length := 4
	if len(ip) > 4 {
		length = 16
	}
	netIP := make(net.IP, length)
	for n := 1; n <= len(ip); n++ {
		netIP[length-n] = ip[len(ip)-n]
	}
	return netIP, nil
}
