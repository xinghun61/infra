// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

import (
	"testing"
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
