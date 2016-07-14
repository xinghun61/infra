package model

var (
	// masters is the list of known Masters.
	masters = []*Master{
		{
			Name:       "ChromiumAndroid",
			Identifier: "chromium.android",
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
			// Swarming staging master.
			Name:       "chromium.swarm",
			Identifier: "chromium.swarm",
			Groups:     []string{"ThisIsUnused"},
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
			Name:       "WebRTC",
			Identifier: "client.webrtc",
			Groups:     []string{"@ToT WebRTC"},
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
)

// Master represents the properties of a master.
type Master struct {
	Name       string
	Identifier string
	Groups     []string
}

// MasterByIdentifier returns the first Master (if any) that has its Identifier
// field equal to ident.
func MasterByIdentifier(ident string) *Master {
	for _, m := range masters {
		if m.Identifier == ident {
			return m
		}
	}
	return nil
}

// MasterByName returns the first Master (if any) that has its Name field equal
// to name.
func MasterByName(name string) *Master {
	for _, m := range masters {
		if m.Name == name {
			return m
		}
	}
	return nil
}
