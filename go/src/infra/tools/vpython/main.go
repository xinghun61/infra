// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os"
	"time"

	"github.com/luci/luci-go/hardcoded/chromeinfra"
	"github.com/luci/luci-go/vpython/api/vpython"
	"github.com/luci/luci-go/vpython/application"
	"github.com/luci/luci-go/vpython/cipd"

	cipdClient "github.com/luci/luci-go/cipd/client/cipd"

	"golang.org/x/net/context"
)

var defaultConfig = application.Config{
	PackageLoader: &cipd.PackageLoader{
		Options: cipdClient.ClientOptions{
			ServiceURL: chromeinfra.CIPDServiceURL,
			UserAgent:  "vpython",
		},
	},
	VENVPackage: vpython.Spec_Package{
		Name:    "infra/python/virtualenv",
		Version: "version:15.1.0",
	},
	PruneThreshold:    7 * 24 * time.Hour, // One week.
	MaxPrunesPerSweep: 3,
	MaxScriptPathLen:  127, // Maximum POSIX shebang length.
}

func main() {
	rv := defaultConfig.Main(context.Background())
	os.Exit(rv)
}
