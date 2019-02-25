// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/system/filesystem"
)

var (
	validHostnameRe = regexp.MustCompile("^[a-zA-Z0-9\\-_.]+$") // good enough
)

// InputError indicates an error in the kitchen's input, e.g. command line flag
// or env variable.
// It is converted to InfraError.INVALID_INPUT defined in the result.proto.
type InputError string

func (e InputError) Error() string { return string(e) }

// inputError returns an error that will be converted to a InfraError with
// type INVALID_INPUT.
func inputError(format string, args ...interface{}) error {
	// We don't use D to keep signature of this function simple
	// and to keep UserError as a leaf.
	return errors.Annotate(InputError(fmt.Sprintf(format, args...)), "").Err()
}

// Normalize normalizes the contents of CookFlags, returning non-nil if there is
// an error.
func (c *CookFlags) Normalize() error {
	if c.CheckoutDir == "" {
		return inputError("empty -checkout-dir")
	}
	switch st, err := os.Stat(c.CheckoutDir); {
	case os.IsNotExist(err):
		return inputError("-checkout-dir doesn't exist")
	case !os.IsNotExist(err) && err != nil:
		return err
	case err == nil && !st.IsDir():
		return inputError("-checkout-dir is not a directory")
	}

	if c.RecipeName == "" {
		return inputError("-recipe is required")
	}

	if len(c.Properties) > 0 && c.PropertiesFile != "" {
		return inputError("only one of -properties or -properties-file is allowed")
	}

	if c.TempDir != "" {
		c.TempDir = filepath.FromSlash(c.TempDir)
		if err := filesystem.AbsPath(&c.TempDir); err != nil {
			return err
		}
	}

	c.OutputResultJSONPath = filepath.FromSlash(c.OutputResultJSONPath)

	// Make sure gerrit hosts indeed look like hostnames.
	for _, value := range c.KnownGerritHost {
		if !validHostnameRe.MatchString(value) {
			return inputError("invalid gerrit hostname %q", value)
		}
	}

	if c.CallUpdateBuild {
		if c.BuildbucketHostname == "" {
			return inputError("-call-update-build requires -buildbucket-hostname")
		}
		if c.BuildbucketBuildID <= 0 {
			return inputError("-call-update-build requires a valid -buildbucket-build-id")
		}
	}

	return c.LogDogFlags.validate()
}
