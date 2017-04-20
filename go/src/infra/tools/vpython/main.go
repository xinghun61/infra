// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/hardcoded/chromeinfra"
	"github.com/luci/luci-go/vpython/api/vpython"
	"github.com/luci/luci-go/vpython/application"
	"github.com/luci/luci-go/vpython/cipd"

	cipdClient "github.com/luci/luci-go/cipd/client/cipd"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
)

var cipdPackageLoader = cipd.PackageLoader{
	Options: cipdClient.ClientOptions{
		ServiceURL: chromeinfra.CIPDServiceURL,
		UserAgent:  "vpython",
	},
	Template: getCIPDTemplatesForEnvironment,
}

var defaultConfig = application.Config{
	PackageLoader: &cipdPackageLoader,
	VENVPackage: vpython.Spec_Package{
		Name:    "infra/python/virtualenv",
		Version: "version:15.1.0",
	},
	PruneThreshold:    7 * 24 * time.Hour, // One week.
	MaxPrunesPerSweep: 3,
	MaxScriptPathLen:  127, // Maximum POSIX shebang length.

	Verification: verificationGen,
}

func mainImpl(c context.Context) int {
	// Initialize our CIPD package loader from the environment.
	if err := cipdPackageLoader.Options.LoadFromEnv(os.Getenv); err != nil {
		logging.Errorf(c, "Could not inialize CIPD package loader: %s", err)
		return 1
	}

	return defaultConfig.Main(c)
}

func main() {
	c := context.Background()
	c = gologger.StdConfig.Use(logging.SetLevel(c, logging.Warning))
	os.Exit(mainImpl(c))
}
