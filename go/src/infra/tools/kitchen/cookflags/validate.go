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
	validRevisionRe = regexp.MustCompile("^([a-z0-9]{40}|HEAD|refs/.+)$")
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
	if c.Mode == InvalidCookMode {
		return inputError("missing mode (-mode)")
	}

	if c.WorkDir == "" {
		return inputError("-workdir is required")
	}

	if c.RepositoryURL != "" && c.Revision == "" {
		c.Revision = "HEAD"
	} else if c.RepositoryURL == "" && c.Revision != "" {
		return inputError("if -repository is unspecified -revision must also be unspecified.")
	}

	if c.RepositoryURL != "" && !validRevisionRe.MatchString(c.Revision) {
		return inputError("invalid revision %q", c.Revision)
	}

	if c.CheckoutDir == "" {
		return inputError("empty -checkout-dir")
	}
	switch st, err := os.Stat(c.CheckoutDir); {
	case os.IsNotExist(err) && c.RepositoryURL == "":
		return inputError("-repository not specified and -checkout-dir doesn't exist")
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

	return c.LogDogFlags.setupAndValidate(c.Mode)
}
