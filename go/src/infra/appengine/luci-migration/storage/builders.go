// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package storage

import (
	"fmt"
	"strings"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/errors"

	"infra/appengine/luci-migration/config"
)

// Builder is a Buildbot builder that needs to be migrated to LUCI.
type Builder struct {
	Kind           string    `gae:"$kind,Builder"`
	ID             BuilderID `gae:"$id"`
	SchedulingType config.SchedulingType
	Public         bool
	OS             config.OS

	IssueID IssueID

	LUCIBuildbucketBucket  string
	LUCIBuildbucketBuilder string
}

// IssueID globally identifies a Monorail issue.
type IssueID struct {
	Hostname string
	Project  string
	ID       int
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
