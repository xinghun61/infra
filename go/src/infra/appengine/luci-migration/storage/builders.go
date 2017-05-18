// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package storage

import (
	"fmt"
	"strings"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/errors"
)

// Builder is a Buildbot builder that needs to be migrated to LUCI.
type Builder struct {
	Kind                   string    `gae:"$kind,Builder"`
	ID                     BuilderID `gae:"$id"`
	SchedulingType         SchedulingType
	Public                 bool
	IssueID                int
	LUCIBuildbucketBucket  string
	LUCIBuildbucketBuilder string
	OS                     OS
}

// BuilderID is a combination of a Buildbot master and builder.
type BuilderID struct {
	Master  string // without "master." prefix
	Builder string
}

// String implements fmt.Stringer.
func (b *BuilderID) String() string {
	return b.Master + ":" + b.Builder
}

// ToProperty implements PropertyConverter.
func (b *BuilderID) ToProperty() (datastore.Property, error) {
	return datastore.MkProperty(b.String()), nil
}

// FromProperty implements PropertyConverter.
func (b *BuilderID) FromProperty(p datastore.Property) error {
	str, ok := p.Value().(string)
	if !ok {
		return fmt.Errorf("not a string")
	}
	parts := strings.SplitN(str, ":", 2)
	if len(parts) != 2 {
		return errors.Reason("no colon in %(id)q").D("id", str).Err()
	}

	b.Master = parts[0]
	b.Builder = parts[1]
	return nil
}

// SchedulingType specifies how builds are scheduled on a builder.
type SchedulingType int

const (
	// TryScheduling means builds are scheduled for CLs.
	TryScheduling SchedulingType = iota
	// ContinuousScheduling means builds are scheduled periodically or
	// for landed commits.
	ContinuousScheduling
)

// OS is an operating system that we care about.
type OS int

const (
	UnknownOS OS = iota
	Linux
	Mac
	Windows
	Android
	IOS
)

// String returns a valid value for OS monorail label.
func (os OS) String() string {
	switch os {
	case UnknownOS:
		return ""
	case Linux:
		return "Linux"
	case Mac:
		return "Mac"
	case Windows:
		return "Windows"
	case Android:
		return "Android"
	case IOS:
		return "iOS"
	default:
		return fmt.Sprintf("invalid os %d", os)
	}
}
