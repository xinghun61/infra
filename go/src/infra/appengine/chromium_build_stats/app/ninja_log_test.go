// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"infra/appengine/chromium_build_stats/ninjalog"
)

func TestNinjalogPath(t *testing.T) {
	testCases := []struct {
		reqPath string
		logPath string
		isErr   bool
	}{
		{
			reqPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz",
			logPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz",
		},
		{
			reqPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz/",
			logPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz",
		},
		{
			reqPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz/lastbuild",
			logPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz",
		},
		{
			reqPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz/metadata.json",
			logPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz",
		},
		{
			reqPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz/trace.json",
			logPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz",
		},
		{
			reqPath: "/2014/09/08/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-204617.14600.gz/unsupported",
			logPath: "",
			isErr:   true,
		},
		{
			reqPath: "/2014/09/08/build48-m1/compiler_proxy.build48-m1.chrome-bot.INFO.20140907-204617.14600.gz",
			logPath: "",
			isErr:   true,
		},
	}

	for i, tc := range testCases {
		logPath, _, err := ninjalogPath(tc.reqPath)
		if tc.isErr {
			if err == nil {
				t.Errorf("%d: ninjalogPath(%q)=_, _, %v; want _, _, <nil>", i, tc.reqPath, err)
			}
			continue
		}
		if err != nil {
			t.Errorf("%d: ninjalogPath(%q)=_, _, %v; want=%q, _, <nil>", i, tc.reqPath, err, tc.logPath)
			continue
		}
		if logPath != tc.logPath {
			// func is not comparable.
			t.Errorf("%d: ninjalogPath(%q)=%q, _, <nil>; want=%q, _, <nil>", i, tc.reqPath, logPath, tc.logPath)
		}
	}
}

func TestTypeFromExt(t *testing.T) {
	testCases := []struct {
		step ninjalog.Step
		want string
	}{
		{
			step: ninjalog.Step{Out: ""},
			want: ".",
		},
		{
			step: ninjalog.Step{Out: "gen/chrome/android/chrome_modern_public_apk/chrome_modern_public_apk.proguard.jar"},
			want: ".proguard.jar",
		},
		{
			step: ninjalog.Step{Out: "headless_browsertests.exe.pdb"},
			want: "PEFile (linking)",
		},
		{
			step: ninjalog.Step{Out: "headless_browsertests.exe"},
			want: "PEFile (linking)",
		},
		{
			step: ninjalog.Step{Out: "headless_browsertests"},
			want: "(no extension found)",
		},
		{
			step: ninjalog.Step{Out: "gen/services/identity/public/mojom/identity_manager.mojom-shared-message-ids.h"},
			want: ".mojom-shared-message-ids.h",
		},
	}

	for _, tc := range testCases {
		got := typeFromExt(tc.step)
		if got != tc.want {
			t.Errorf("typeFromText(%q)=%s; want=%s", tc.step, got, tc.want)
		}
	}
}
