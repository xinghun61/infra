// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os"
	"path/filepath"
	"runtime"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/hardcoded/chromeinfra"
	"github.com/luci/luci-go/vpython/api/vpython"
	"github.com/luci/luci-go/vpython/application"
	"github.com/luci/luci-go/vpython/cipd"

	cipdClient "github.com/luci/luci-go/cipd/client/cipd"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/mitchellh/go-homedir"
)

var cipdPackageLoader = cipd.PackageLoader{
	Options: cipdClient.ClientOptions{
		ServiceURL: chromeinfra.CIPDServiceURL,
		UserAgent:  "vpython",
	},
	Template: func(c context.Context, e *vpython.Environment) (map[string]string, error) {
		tag := pep425TagSelector(runtime.GOOS, e.Pep425Tag)
		if tag == nil {
			return nil, nil
		}
		return getPEP425CIPDTemplateForTag(tag)
	},
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
}

func mainImpl(c context.Context) int {
	// Initialize our CIPD package loader from the environment.
	//
	// If we don't have an environment-specific CIPD cache directory, use one
	// relative to the user's home directory.
	if err := cipdPackageLoader.Options.LoadFromEnv(os.Getenv); err != nil {
		logging.Errorf(c, "Could not inialize CIPD package loader: %s", err)
		return 1
	}
	if cipdPackageLoader.Options.CacheDir == "" {
		hd, err := homedir.Dir()
		if err == nil {
			cipdPackageLoader.Options.CacheDir = filepath.Join(hd, ".vpython_cipd_cache")
		} else {
			logging.WithError(err).Warningf(c,
				"Failed to resolve user home directory. No CIPD cache will be enabled.")
		}
	}

	defaultConfig.WithVerificationConfig = withVerificationConfig
	return defaultConfig.Main(c)
}

func main() {
	c := context.Background()
	c = gologger.StdConfig.Use(logging.SetLevel(c, logging.Warning))
	os.Exit(mainImpl(c))
}
