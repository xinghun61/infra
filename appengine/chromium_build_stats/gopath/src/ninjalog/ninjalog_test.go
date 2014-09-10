// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ninjalog

import (
	"bytes"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"
)

var (
	logTestCase = `# ninja log v5
76	187	0	resources/inspector/devtools_extension_api.js	75430546595be7c2
80	284	0	gen/autofill_regex_constants.cc	fa33c8d7ce1d8791
78	286	0	gen/angle/commit_id.py	4ede38e2c1617d8c
79	287	0	gen/angle/copy_compiler_dll.bat	9fb635ad5d2c1109
141	287	0	PepperFlash/manifest.json	324f0a0b77c37ef
142	288	0	PepperFlash/libpepflashplayer.so	1e2c2b7845a4d4fe
287	290	0	obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp	b211d373de72f455
`

	stepsTestCase = []Step{
		Step{
			Start:   76 * time.Millisecond,
			End:     187 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "resources/inspector/devtools_extension_api.js",
			CmdHash: "75430546595be7c2",
		},
		Step{
			Start:   80 * time.Millisecond,
			End:     284 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "gen/autofill_regex_constants.cc",
			CmdHash: "fa33c8d7ce1d8791",
		},
		Step{
			Start:   78 * time.Millisecond,
			End:     286 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "gen/angle/commit_id.py",
			CmdHash: "4ede38e2c1617d8c",
		},
		Step{
			Start:   79 * time.Millisecond,
			End:     287 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "gen/angle/copy_compiler_dll.bat",
			CmdHash: "9fb635ad5d2c1109",
		},
		Step{
			Start:   141 * time.Millisecond,
			End:     287 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "PepperFlash/manifest.json",
			CmdHash: "324f0a0b77c37ef",
		},
		Step{
			Start:   142 * time.Millisecond,
			End:     288 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "PepperFlash/libpepflashplayer.so",
			CmdHash: "1e2c2b7845a4d4fe",
		},
		Step{
			Start:   287 * time.Millisecond,
			End:     290 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp",
			CmdHash: "b211d373de72f455",
		},
	}

	stepsSorted = []Step{
		Step{
			Start:   76 * time.Millisecond,
			End:     187 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "resources/inspector/devtools_extension_api.js",
			CmdHash: "75430546595be7c2",
		},
		Step{
			Start:   78 * time.Millisecond,
			End:     286 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "gen/angle/commit_id.py",
			CmdHash: "4ede38e2c1617d8c",
		},
		Step{
			Start:   79 * time.Millisecond,
			End:     287 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "gen/angle/copy_compiler_dll.bat",
			CmdHash: "9fb635ad5d2c1109",
		},
		Step{
			Start:   80 * time.Millisecond,
			End:     284 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "gen/autofill_regex_constants.cc",
			CmdHash: "fa33c8d7ce1d8791",
		},
		Step{
			Start:   141 * time.Millisecond,
			End:     287 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "PepperFlash/manifest.json",
			CmdHash: "324f0a0b77c37ef",
		},
		Step{
			Start:   142 * time.Millisecond,
			End:     288 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "PepperFlash/libpepflashplayer.so",
			CmdHash: "1e2c2b7845a4d4fe",
		},
		Step{
			Start:   287 * time.Millisecond,
			End:     290 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     "obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp",
			CmdHash: "b211d373de72f455",
		},
	}

	metadataTestCase = Metadata{
		Platform: "linux",
		Argv:     []string{"../../../scripts/slave/compile.py", "--target", "Release", "--clobber", "--compiler=goma", "--", "all"},
		Cwd:      "/b/build/slave/Linux_x64/build/src",
		Compiler: "goma",
		Cmdline:  []string{"ninja", "-C", "/b/build/slave/Linux_x64/build/src/out/Release", "all", "-j50"},
		Exit:     0,
		Env: map[string]string{
			"LANG":    "en_US.UTF-8",
			"SHELL":   "/bin/bash",
			"HOME":    "/home/chrome-bot",
			"PWD":     "/b/build/slave/Linux_x64/build",
			"LOGNAME": "chrome-bot",
			"USER":    "chrome-bot",
			"PATH":    "/home/chrome-bot/slavebin:/b/depot_tools:/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin",
		},
		CompilerProxyInfo: "/tmp/compiler_proxy.build48-m1.chrome-bot.log.INFO.20140907-203827.14676",
	}
)

func TestStepsSort(t *testing.T) {
	steps := append([]Step{}, stepsTestCase...)
	sort.Sort(Steps(steps))
	if !reflect.DeepEqual(steps, stepsSorted) {
		t.Errorf("sort Steps=%v; want=%v", steps, stepsSorted)
	}
}

func TestStepsReverse(t *testing.T) {
	steps := []Step{
		Step{Out: "0"},
		Step{Out: "1"},
		Step{Out: "2"},
		Step{Out: "3"},
	}
	Steps(steps).Reverse()
	want := []Step{
		Step{Out: "3"},
		Step{Out: "2"},
		Step{Out: "1"},
		Step{Out: "0"},
	}
	if !reflect.DeepEqual(steps, want) {
		t.Errorf("steps.Reverse=%v; want=%v", steps, want)
	}
}

func TestParseBadVersion(t *testing.T) {
	_, err := Parse(strings.NewReader(`# ninja log v4
0	1	0	foo	touch foo
`))
	if err == nil {
		t.Error("Parse()=_, <nil>; want=_, error")
	}
}

func TestParseSimple(t *testing.T) {
	njl, err := Parse(strings.NewReader(logTestCase))
	if err != nil {
		t.Errorf(`Parse()=_, %v; want=_, <nil>`, err)
	}

	want := &NinjaLog{
		Start: 1,
		Steps: stepsTestCase,
	}
	if !reflect.DeepEqual(njl, want) {
		t.Errorf("Parse()=%v; want=%v", njl, want)
	}
}

func TestParseLast(t *testing.T) {
	njl, err := Parse(strings.NewReader(`# ninja log v5
1020807	1020916	0	chrome.1	e101fd46be020cfc
84	9489	0	gen/libraries.cc	9001f3182fa8210e
1024369	1041522	0	chrome	aee9d497d56c9637
76	187	0	resources/inspector/devtools_extension_api.js	75430546595be7c2
80	284	0	gen/autofill_regex_constants.cc	fa33c8d7ce1d8791
78	286	0	gen/angle/commit_id.py	4ede38e2c1617d8c
79	287	0	gen/angle/copy_compiler_dll.bat	9fb635ad5d2c1109
141	287	0	PepperFlash/manifest.json	324f0a0b77c37ef
142	288	0	PepperFlash/libpepflashplayer.so	1e2c2b7845a4d4fe
287	290	0	obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp	b211d373de72f455
`))
	if err != nil {
		t.Errorf(`Parse()=_, %v; want=_, <nil>`, err)
	}

	want := &NinjaLog{
		Start: 4,
		Steps: stepsTestCase,
	}
	if !reflect.DeepEqual(njl, want) {
		t.Errorf("Parse()=%v; want=%v", njl, want)
	}
}

func TestParseMetadata(t *testing.T) {
	njl, err := Parse(strings.NewReader(`# ninja log v5
1020807	1020916	0	chrome.1	e101fd46be020cfc
84	9489	0	gen/libraries.cc	9001f3182fa8210e
1024369	1041522	0	chrome	aee9d497d56c9637
76	187	0	resources/inspector/devtools_extension_api.js	75430546595be7c2
80	284	0	gen/autofill_regex_constants.cc	fa33c8d7ce1d8791
78	286	0	gen/angle/commit_id.py	4ede38e2c1617d8c
79	287	0	gen/angle/copy_compiler_dll.bat	9fb635ad5d2c1109
141	287	0	PepperFlash/manifest.json	324f0a0b77c37ef
142	288	0	PepperFlash/libpepflashplayer.so	1e2c2b7845a4d4fe
287	290	0	obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp	b211d373de72f455
# end of ninja log
{"platform": "linux", "argv": ["../../../scripts/slave/compile.py", "--target", "Release", "--clobber", "--compiler=goma", "--", "all"], "cmdline": ["ninja", "-C", "/b/build/slave/Linux_x64/build/src/out/Release", "all", "-j50"], "exit": 0, "env": {"LANG": "en_US.UTF-8", "SHELL": "/bin/bash", "HOME": "/home/chrome-bot", "PWD": "/b/build/slave/Linux_x64/build", "LOGNAME": "chrome-bot", "USER": "chrome-bot", "PATH": "/home/chrome-bot/slavebin:/b/depot_tools:/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin" }, "compiler_proxy_info": "/tmp/compiler_proxy.build48-m1.chrome-bot.log.INFO.20140907-203827.14676", "cwd": "/b/build/slave/Linux_x64/build/src", "compiler": "goma"}
`))
	if err != nil {
		t.Errorf(`Parse()=_, %v; want=_, <nil>`, err)
	}

	want := &NinjaLog{
		Start:    4,
		Steps:    stepsTestCase,
		Metadata: metadataTestCase,
	}
	if !reflect.DeepEqual(njl, want) {
		t.Errorf("Parse()=%v; want=%v", njl, want)
	}
}

func TestDump(t *testing.T) {
	var b bytes.Buffer
	err := Dump(&b, stepsTestCase)
	if err != nil {
		t.Errorf("Dump()=%v; want=<nil>", err)
	}
	if b.String() != logTestCase {
		t.Errorf("Dump %q; want %q", b.String(), logTestCase)
	}
}

func TestDedup(t *testing.T) {
	steps := append([]Step{}, stepsTestCase...)
	for _, out := range []string{
		"gen/ui/keyboard/webui/keyboard.mojom.cc",
		"gen/ui/keyboard/webui/keyboard.mojom.h",
		"gen/ui/keyboard/webui/keyboard.mojom.js",
		"gen/ui/keyboard/webui/keyboard.mojom-internal.h",
	} {
		steps = append(steps, Step{
			Start:   302 * time.Millisecond,
			End:     5764 * time.Millisecond,
			Restat:  time.Unix(0, 0),
			Out:     out,
			CmdHash: "a551cc46f8c21e5a",
		})
	}
	got := Dedup(steps)
	want := append([]Step{}, stepsSorted...)
	want = append(want, Step{
		Start:   302 * time.Millisecond,
		End:     5764 * time.Millisecond,
		Restat:  time.Unix(0, 0),
		Out:     "gen/ui/keyboard/webui/keyboard.mojom-internal.h",
		CmdHash: "a551cc46f8c21e5a",
	})
	if !reflect.DeepEqual(got, want) {
		t.Errorf("Dedup=%v; want=%v", got, want)
	}
}

func TestFlow(t *testing.T) {
	steps := append([]Step{}, stepsTestCase...)
	steps = append(steps, Step{
		Start:   187 * time.Millisecond,
		End:     21304 * time.Millisecond,
		Restat:  time.Unix(0, 0),
		Out:     "obj/third_party/pdfium/core/src/fpdfdoc/fpdfdoc.doc_formfield.o",
		CmdHash: "2ac7111aa1ae86af",
	})

	flow := Flow(steps)

	want := [][]Step{
		[]Step{
			Step{
				Start:   76 * time.Millisecond,
				End:     187 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "resources/inspector/devtools_extension_api.js",
				CmdHash: "75430546595be7c2",
			},
			Step{
				Start:   187 * time.Millisecond,
				End:     21304 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "obj/third_party/pdfium/core/src/fpdfdoc/fpdfdoc.doc_formfield.o",
				CmdHash: "2ac7111aa1ae86af",
			},
		},
		[]Step{
			Step{
				Start:   78 * time.Millisecond,
				End:     286 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "gen/angle/commit_id.py",
				CmdHash: "4ede38e2c1617d8c",
			},
			Step{
				Start:   287 * time.Millisecond,
				End:     290 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp",
				CmdHash: "b211d373de72f455",
			},
		},
		[]Step{
			Step{
				Start:   79 * time.Millisecond,
				End:     287 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "gen/angle/copy_compiler_dll.bat",
				CmdHash: "9fb635ad5d2c1109",
			},
		},
		[]Step{
			Step{
				Start:   80 * time.Millisecond,
				End:     284 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "gen/autofill_regex_constants.cc",
				CmdHash: "fa33c8d7ce1d8791",
			},
		},
		[]Step{
			Step{
				Start:   141 * time.Millisecond,
				End:     287 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "PepperFlash/manifest.json",
				CmdHash: "324f0a0b77c37ef",
			},
		},
		[]Step{
			Step{
				Start:   142 * time.Millisecond,
				End:     288 * time.Millisecond,
				Restat:  time.Unix(0, 0),
				Out:     "PepperFlash/libpepflashplayer.so",
				CmdHash: "1e2c2b7845a4d4fe",
			},
		},
	}

	if !reflect.DeepEqual(flow, want) {
		t.Errorf("Flow()=%v; want=%v", flow, want)
	}
}
