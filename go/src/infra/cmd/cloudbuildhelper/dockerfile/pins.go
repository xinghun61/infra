// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"fmt"
	"io"
	"io/ioutil"
	"sort"
	"strings"

	"gopkg.in/yaml.v2"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/sync/parallel"
)

// Pins is a mapping (image name, tag) => digest.
type Pins struct {
	Pins []Pin `yaml:"pins"`
}

// Pin is a single "(image name, tag) => digest" pin.
type Pin struct {
	Comment string `yaml:"comment,omitempty"` // arbitrary string, for humans
	Image   string `yaml:"image"`             // required
	Tag     string `yaml:"tag,omitempty"`     // default is "latest"
	Digest  string `yaml:"digest"`            // required
	Freeze  string `yaml:"freeze,omitempty"`  // if set, don't update in pins-update
}

func (p *Pin) key() string {
	return p.Image + ":" + p.Tag
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
	seen := stringset.New(len(out.Pins))
	for idx, p := range out.Pins {
		if p, err = normalizePin(p); err != nil {
			return nil, errors.Annotate(err, "pin #%d", idx+1).Err()
		}
		if !seen.Add(p.key()) {
			return nil, errors.Reason("pin #%d: duplicate entry for %q", idx+1, p.key()).Err()
		}
		out.Pins[idx] = p
	}
	return &out, nil
}

// WritePins generates YAML with pins.
//
// Entries are normalized and sorted.
func WritePins(w io.Writer, p *Pins) error {
	pins := Pins{Pins: append([]Pin(nil), p.Pins...)}
	sort.Slice(pins.Pins, func(i, j int) bool {
		l, r := pins.Pins[i], pins.Pins[j]
		if l.Image == r.Image {
			return l.Tag < r.Tag
		}
		return l.Image < r.Image
	})

	blob, err := yaml.Marshal(pins)
	if err != nil {
		return errors.Annotate(err, "failed to serialize pins").Err()
	}

	_, err = fmt.Fprintf(w, `# Managed by cloudbuildhelper.
#
# All comments or unrecognized fields will be overwritten. To comment an entry
# use "comment" field.
#
# To update digests of all entries:
#   $ cloudbuildhelper pins-update <path-to-this-file>
#
# To add an entry (or update an existing one):
#   $ cloudbuildhelper pins-add <path-to-this-file> <image>[:<tag>]
#
# To remove an entry just delete it from the file.
#
# To prevent an entry from being updated by pins-update, add "freeze" field with
# an explanation why it is frozen.

%s`, blob)

	return errors.Annotate(err, "failed to write").Err()
}

// Add adds or updates a pin (which should already be resolved).
func (p *Pins) Add(pin Pin) error {
	pin, err := normalizePin(pin)
	if err != nil {
		return err
	}

	key := pin.key()
	for i := range p.Pins {
		if p.Pins[i].key() == key {
			p.Pins[i] = pin
			return nil
		}
	}

	p.Pins = append(p.Pins, pin)
	return nil
}

// Visit calls 'cb' concurrently for all pins.
//
// The callback can mutate any pin fields except Image and Tag (doing so will
// panic).
//
// Calls the callback even for pins that are marked as frozen. The callback
// should handle this itself (e.g. by logging and skipping them).
//
// Returns a multi-error with all errors that happened.
func (p *Pins) Visit(cb func(p *Pin) error) error {
	return parallel.WorkPool(16, func(tasks chan<- func() error) {
		for i := range p.Pins {
			i := i
			tasks <- func() error {
				pin := p.Pins[i]
				key := pin.key()
				if err := cb(&pin); err != nil {
					return errors.Annotate(err, "when visiting %q", key).Err()
				}
				pin, err := normalizePin(pin)
				if err != nil {
					return errors.Annotate(err, "when visiting %q", key).Err()
				}
				if pin.key() != key {
					panic(fmt.Sprintf("the callback changed the pin key from %q to %q", key, pin.key()))
				}
				p.Pins[i] = pin
				return nil
			}
		}
	})
}

func normalizePin(p Pin) (Pin, error) {
	switch {
	case p.Image == "":
		return p, errors.Reason("'image' field is required").Err()
	case p.Digest == "":
		return p, errors.Reason("'digest' field is required").Err()
	}
	// See https://github.com/docker/distribution/blob/master/reference/normalize.go
	// for defaults.
	switch strings.Count(p.Image, "/") {
	case 0: // e.g. "ubuntu"
		p.Image = "docker.io/library/" + p.Image
	case 1: // e.g. "library/ubuntu"
		p.Image = "docker.io/" + p.Image
	default: // e.g. "gcr.io/something/something", do nothing, good enough
	}
	if p.Tag == "" {
		p.Tag = "latest"
	}
	return p, nil
}

// Resolver returns a Resolver that uses a snapshot of Pins as a source.
func (p *Pins) Resolver() Resolver {
	m := make(pinsResolver, len(p.Pins))
	for _, pin := range p.Pins {
		m[pin.key()] = pin.Digest
	}
	return m
}

type pinsResolver map[string]string

func (p pinsResolver) ResolveTag(image, tag string) (digest string, err error) {
	if len(p) == 0 {
		return "", errors.Reason("not using pins YAML, the Dockerfile must use @<digest> refs").Err()
	}

	pin, err := normalizePin(Pin{
		Image:  image,
		Tag:    tag,
		Digest: "to-be-resolved", // to pass validation, we don't use this field
	})
	if err != nil {
		return "", errors.Annotate(err, "bad image:tag combination").Err()
	}

	d, ok := p[pin.key()]
	if !ok {
		// Note: the outer error wrapper usually has enough context already, adding
		// 'image' and 'tag' values here causes duplication.
		return "", errors.Reason("no such pinned <image>:<tag> combination in pins YAML").Err()
	}
	return d, nil
}
