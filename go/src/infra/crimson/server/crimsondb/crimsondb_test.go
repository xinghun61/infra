package crimsondb

import (
	"testing"
)

func TestIPStringToHexString(t *testing.T) {
	hexString := IPStringToHexString("192.168.0.1")
	expected := "0xc0a80001"
	if hexString != expected {
		t.Error("Hex string is different from expected value:",
			hexString, "vs", expected)
	}

	hexString = IPStringToHexString("0.0.0.0")
	expected = "0x00000000"
	if hexString != expected {
		t.Error("Hex string is different from expected value:",
			hexString, "vs", expected)
	}
}

func TestHexStringToIPString(t *testing.T) {
	ipString := HexStringToIP("0x00000000").String()
	expected := "0.0.0.0"
	if ipString != expected {
		t.Error("IP string is different from expected value:",
			ipString, "vs", expected)
	}

	ipString = HexStringToIP("0xc0a80001").String()
	expected = "192.168.0.1"
	if ipString != expected {
		t.Error("IP string is different from expected value:",
			ipString, "vs", expected)
	}
}

func TestIPStringToHexAndBack(t *testing.T) {
	// Check that function which are supposed to be exact inverse actually are.
	ip1 := "135.45.1.84"
	ip2 := HexStringToIP(IPStringToHexString(ip1)).String()
	if ip1 != ip2 {
		t.Error("IP string is different from expected value:",
			ip1, "vs", ip2)
	}

	ip1 = "1.2.3.4"
	ip2 = HexStringToIP(IPStringToHexString(ip1)).String()
	if ip1 != ip2 {
		t.Error("IP string is different from expected value:",
			ip1, "vs", ip2)
	}

	ip1 = "255.255.255.255"
	ip2 = HexStringToIP(IPStringToHexString(ip1)).String()
	if ip1 != ip2 {
		t.Error("IP string is different from expected value:",
			ip1, "vs", ip2)
	}
}
