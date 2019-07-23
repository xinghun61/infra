// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"fmt"
	"io"
	"io/ioutil"
	"strings"

	"gopkg.in/yaml.v2"

	"go.chromium.org/luci/common/errors"
)

// Pins is a mapping (image name, tag) => digest.
type Pins struct {
	Pins []Pin `yaml:"pins"`
}

// Pin is a single "(image name, tag) => digest" pin.
type Pin struct {
	Image  string `yaml:"image"`         // required
	Tag    string `yaml:"tag,omitempty"` // default is "latest"
	Digest string `yaml:"digest"`        // required
}

// ReadPins loads and validates YAML file with pins.
func ReadPins(r io.Reader) (*Pins, error) {
	body, err := ioutil.ReadAll(r)
	if err != nil {
		return nil, errors.Annotate(err, "failed to read the pins file").Err()
	}
	out := Pins{}
	if err = yaml.Unmarshal(body, &out); err != nil {
		return nil, errors.Annotate(err, "failed to parse the pins file").Err()
	}
	for idx, p := range out.Pins {
		if err := validatePin(p); err != nil {
			return nil, errors.Annotate(err, "pin #%d", idx+1).Err()
		}
	}
	return &out, nil
}

func validatePin(p Pin) error {
	switch {
	case p.Image == "":
		return errors.Reason("'image' field is required").Err()
	case p.Digest == "":
		return errors.Reason("'digest' field is required").Err()
	default:
		return nil
	}
}

// Resolver returns a Resolver that uses a snapshot of Pins as a source.
func (p *Pins) Resolver() Resolver {
	m := make(pinsResolver, len(p.Pins))
	for _, pin := range p.Pins {
		m[pinKey(pin.Image, pin.Tag)] = pin.Digest
	}
	return m
}

func pinKey(img, tag string) string {
	// See https://github.com/docker/distribution/blob/master/reference/normalize.go
	// for defaults.
	switch strings.Count(img, "/") {
	case 0: // e.g. "ubuntu"
		img = "docker.io/library/" + img
	case 1: // e.g. "library/ubuntu"
		img = "docker.io/" + img
	default: // e.g. "gcr.io/something/something", do nothing, good enough
	}
	if tag == "" {
		tag = "latest"
	}
	return fmt.Sprintf("%s:%s", img, tag)
}

type pinsResolver map[string]string

func (p pinsResolver) ResolveTag(image, tag string) (digest string, err error) {
	if len(p) == 0 {
		return "", errors.Reason("not using pins YAML, the Dockerfile must use @<digest> refs").Err()
	}
	d, ok := p[pinKey(image, tag)]
	if !ok {
		// Note: the outer error wrapper usually has enough context already, adding
		// 'image' and 'tag' values here causes duplication.
		return "", errors.Reason("no such pinned <image>:<tag> combination in pins YAML").Err()
	}
	return d, nil
}
