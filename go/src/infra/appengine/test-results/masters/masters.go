// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package masters provides a list of known masters.
package masters

// Known is the list of known masters.
var Known = []*Master{
	{
		Name:       "ChromiumAndroid",
		Identifier: "chromium.android",
	},
	{
		Name:       "ChromiumAndroidFyi",
		Identifier: "chromium.android.fyi",
	},
	{
		Name:       "ChromiumChromiumOS",
		Identifier: "chromium.chromiumos",
	},
	{
		Name:       "ChromiumFYI",
		Identifier: "chromium.fyi",
	},
	{
		Name:       "ChromiumGoma",
		Identifier: "chromium.goma",
	},
	{
		Name:       "ChromiumGPU",
		Identifier: "chromium.gpu",
	},
	{
		Name:       "ChromiumGPUFYI",
		Identifier: "chromium.gpu.fyi",
	},
	{
		Name:       "ChromiumLinux",
		Identifier: "chromium.linux",
	},
	{
		Name:       "ChromiumMac",
		Identifier: "chromium.mac",
	},
	{
		Name:       "ChromiumMemory",
		Identifier: "chromium.memory",
	},
	{
		Name:       "ChromiumPerf",
		Identifier: "chromium.perf",
	},
	{
		Name:       "ChromiumPerfFYI",
		Identifier: "chromium.perf.fyi",
	},
	{
		Name:       "ChromiumLUCISandbox",
		Identifier: "chromium.sandbox",
	},
	{
		Name:       "chromium.swarm",
		Identifier: "chromium.swarm",
	},
	{
		Name:       "ChromiumWebRTC",
		Identifier: "chromium.webrtc",
	},
	{
		Name:       "ChromiumWebRTCFYI",
		Identifier: "chromium.webrtc.fyi",
	},
	{
		Name:       "ChromiumWebkit",
		Identifier: "chromium.webkit",
	},
	{
		Name:       "ChromiumWin",
		Identifier: "chromium.win",
	},
	{
		Name:       "V8Chromium",
		Identifier: "client.v8.chromium",
	},
	{
		Name:       "V8FYI",
		Identifier: "client.v8.fyi",
	},
	{
		Name:       "V8TryServer",
		Identifier: "tryserver.v8",
	},
	{
		Name:       "WebRTC",
		Identifier: "client.webrtc",
	},
	{
		Name:       "WebRTCFYI",
		Identifier: "client.webrtc.fyi",
	},
	{
		Name:       "WebRTCPerf",
		Identifier: "client.webrtc.perf",
	},
	{
		Name:       "WebRTCTryServer",
		Identifier: "tryserver.webrtc",
	},
	{
		Name:       "BlinkTryServer",
		Identifier: "tryserver.blink",
	},
	{
		Name:       "TryserverChromiumAndroid",
		Identifier: "tryserver.chromium.android",
	},
	{
		Name:       "TryserverChromiumAngle",
		Identifier: "tryserver.chromium.angle",
	},
	{
		Name:       "TryServerChromiumLinux",
		Identifier: "tryserver.chromium.linux",
	},
	{
		Name:       "TryServerChromiumMac",
		Identifier: "tryserver.chromium.mac",
	},
	{
		Name:       "TryServerChromiumWin",
		Identifier: "tryserver.chromium.win",
	},
}

// Master represents the properties of a master.
type Master struct {
	Name       string
	Identifier string
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
