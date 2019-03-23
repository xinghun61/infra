// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"os"
	"path/filepath"
	"regexp"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/system/filesystem"
)

var (
	validHostnameRe = regexp.MustCompile("^[a-zA-Z0-9\\-_.]+$") // good enough
)

// Normalize normalizes the contents of CookFlags, returning non-nil if there is
// an error.
func (c *CookFlags) Normalize() error {
	if c.CheckoutDir == "" {
		return errors.Reason("empty -checkout-dir").Err()
	}
	switch st, err := os.Stat(c.CheckoutDir); {
	case os.IsNotExist(err):
		return errors.Reason("-checkout-dir doesn't exist").Err()
	case !os.IsNotExist(err) && err != nil:
		return err
	case err == nil && !st.IsDir():
		return errors.Reason("-checkout-dir is not a directory").Err()
	}

	if c.RecipeName == "" {
		return errors.Reason("-recipe is required").Err()
	}

	if len(c.Properties) > 0 && c.PropertiesFile != "" {
		return errors.Reason("only one of -properties or -properties-file is allowed").Err()
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
			return errors.Reason("invalid gerrit hostname %q", value).Err()
		}
	}

	if c.CallUpdateBuild {
		if c.BuildbucketHostname == "" {
			return errors.Reason("-call-update-build requires -buildbucket-hostname").Err()
		}
		if c.BuildbucketBuildID <= 0 {
			return errors.Reason("-call-update-build requires a valid -buildbucket-build-id").Err()
		}
	}

	if c.AnnotationURL.IsZero() {
		return errors.Reason("-logdog-annotation-url is required").Err()
	}

	return nil
}
