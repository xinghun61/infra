// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package masters provides a list of known masters.
package masters

// Known is the list of known masters.
//
// TODO(estaab): Remove Groups field. It is unused, but was
// ported initially to be consistent with the Python
// implementation.
var Known = []*Master{
	{
		Name:       "ChromiumAndroid",
		Identifier: "chromium.android",
		Groups:     []string{"Unused"},
	},
	{
		Name:       "ChromiumAndroidFyi",
		Identifier: "chromium.android.fyi",
		Groups:     []string{"Unused"},
	},
	{
		Name:       "ChromiumChromiumOS",
		Identifier: "chromium.chromiumos",
		Groups:     []string{"@ToT ChromeOS"},
	},
	{
		Name:       "ChromiumFYI",
		Identifier: "chromium.fyi",
		Groups:     []string{"@ToT Chromium FYI"},
	},
	{
		Name:       "ChromiumGPU",
		Identifier: "chromium.gpu",
		Groups:     []string{"@ToT Chromium"},
	},
	{
		Name:       "ChromiumGPUFYI",
		Identifier: "chromium.gpu.fyi",
		Groups:     []string{"@ToT Chromium FYI"},
	},
	{
		Name:       "ChromiumLinux",
		Identifier: "chromium.linux",
		Groups:     []string{"@ToT Chromium"},
	},
	{
		Name:       "ChromiumMac",
		Identifier: "chromium.mac",
		Groups:     []string{"@ToT Chromium"},
	},
	{
		Name:       "ChromiumMemory",
		Identifier: "chromium.memory",
		Groups:     []string{},
	},
	{
		Name:       "ChromiumMemoryFull",
		Identifier: "chromium.memory.full",
		Groups:     []string{},
	},
	{
		Name:       "chromium.swarm",
		Identifier: "chromium.swarm",
		Groups:     []string{"ThisIsUnused"},
	},
	{
		Name:       "ChromiumWebRTC",
		Identifier: "chromium.webrtc",
		Groups:     []string{"@ToT Chromium"},
	},
	{
		Name:       "ChromiumWebRTCFYI",
		Identifier: "chromium.webrtc.fyi",
		Groups:     []string{"@ToT Chromium", "@ToT WebRTC"},
	},
	{
		Name:       "ChromiumWebkit",
		Identifier: "chromium.webkit",
		Groups:     []string{"@ToT Chromium", "@ToT Blink"},
	},
	{
		Name:       "ChromiumWin",
		Identifier: "chromium.win",
		Groups:     []string{"@ToT Chromium"},
	},
	{
		Name:       "client.mojo",
		Identifier: "client.mojo",
		Groups:     []string{"ThisIsUnused"},
	},
	{
		Name:       "V8",
		Identifier: "client.v8",
		Groups:     []string{"@ToT V8"},
	},
	{
		Name:       "V8FYI",
		Identifier: "client.v8.fyi",
		Groups:     []string{},
	},
	{
		Name:       "V8TryServer",
		Identifier: "tryserver.v8",
		Groups:     []string{},
	},
	{
		Name:       "WebRTC",
		Identifier: "client.webrtc",
		Groups:     []string{"@ToT WebRTC"},
	},
	{
		Name:       "WebRTCFYI",
		Identifier: "client.webrtc.fyi",
		Groups:     []string{},
	},
	{
		Name:       "WebRTCTryServer",
		Identifier: "tryserver.webrtc",
		Groups:     []string{},
	},
	{
		Name:       "BlinkTryServer",
		Identifier: "tryserver.blink",
		Groups:     []string{"Unused"},
	},
	{
		Name:       "TryserverChromiumAndroid",
		Identifier: "tryserver.chromium.android",
		Groups:     []string{"Unused"},
	},
	{
		Name:       "TryServerChromiumLinux",
		Identifier: "tryserver.chromium.linux",
		Groups:     []string{"Unused"},
	},
	{
		Name:       "TryServerChromiumMac",
		Identifier: "tryserver.chromium.mac",
		Groups:     []string{"Unused"},
	},
	{
		Name:       "TryServerChromiumWin",
		Identifier: "tryserver.chromium.win",
		Groups:     []string{"Unused"},
	},
}

// Master represents the properties of a master.
type Master struct {
	Name       string
	Identifier string
	Groups     []string
}

// ByIdentifier returns the first Master (if any) in the list of
// known masters that has its Identifier field equal to ident.
func ByIdentifier(ident string) *Master {
	for _, m := range Known {
		if m.Identifier == ident {
			return m
		}
	}
	return nil
}

// ByName returns the first Master (if any) in the list of
// known masters that has its Name field equal to name.
func ByName(name string) *Master {
	for _, m := range Known {
		if m.Name == name {
			return m
		}
	}
	return nil
}
