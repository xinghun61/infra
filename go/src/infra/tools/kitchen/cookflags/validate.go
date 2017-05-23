// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/stringlistflag"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/system/filesystem"
)

var validRevisionRe = regexp.MustCompile("^([a-z0-9]{40}|HEAD|refs/.+)$")

// InputError indicates an error in the kitchen's input, e.g. command line flag
// or env variable.
// It is converted to KitchenError.INVALID_INPUT defined in the result.proto.
type InputError string

func (e InputError) Error() string { return string(e) }

// inputError returns an error that will be converted to a KitchenError with
// type INVALID_INPUT.
func inputError(format string, args ...interface{}) error {
	// We don't use D to keep signature of this function simple
	// and to keep UserError as a leaf.
	return errors.Annotate(InputError(fmt.Sprintf(format, args...))).Err()
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

	if c.Properties != "" && c.PropertiesFile != "" {
		return inputError("only one of -properties or -properties-file is allowed")
	}

	// normalizePathSlice normalizes a slice of forward-slash-delimited path
	// strings.
	//
	// This operation is destructive, as the normalized result uses the same
	// backing array as the initial path slice.
	normalizePathSlice := func(sp *stringlistflag.Flag) error {
		s := *sp
		seen := make(map[string]struct{}, len(s))
		normalized := s[:0]
		for _, p := range s {
			p := filepath.FromSlash(p)
			if err := filesystem.AbsPath(&p); err != nil {
				return err
			}
			if _, ok := seen[p]; ok {
				continue
			}
			seen[p] = struct{}{}
			normalized = append(normalized, p)
		}

		*sp = normalized
		return nil
	}

	// Normalize c.PythonPaths
	if err := normalizePathSlice(&c.PythonPaths); err != nil {
		return err
	}

	// Normalize c.PrefixPathENV
	if err := normalizePathSlice(&c.PrefixPathENV); err != nil {
		return err
	}

	// Normalize c.SetEnvAbspath
	for i, entry := range c.SetEnvAbspath {
		key, value := environ.Split(entry)
		if value == "" {
			return inputError("-set-env-abspath requires a PATH value")
		}
		if err := filesystem.AbsPath(&value); err != nil {
			return err
		}
		c.SetEnvAbspath[i] = environ.Join(key, value)
	}

	if c.TempDir != "" {
		c.TempDir = filepath.FromSlash(c.TempDir)
		if err := filesystem.AbsPath(&c.TempDir); err != nil {
			return err
		}
	}

	c.OutputResultJSONPath = filepath.FromSlash(c.OutputResultJSONPath)

	return c.LogDogFlags.setupAndValidate(c.Mode)
}
