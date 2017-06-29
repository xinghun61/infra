// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package storage

import (
	"fmt"
	"strings"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/errors"

	"infra/appengine/luci-migration/config"
)

// BuilderKind is kind of Builder entities.
const BuilderKind = "Builder"

const builderIDSep = ':' // must have byte length of 1

// BuilderMasterFilter limits a builder query to builders of the master.
func BuilderMasterFilter(c context.Context, q *datastore.Query, master string) *datastore.Query {
	q = q.Gt("__key__", datastore.NewKey(c, BuilderKind, master+string(builderIDSep), 0, nil))
	// ';' is the next rune after ':'. master name cannot have ':' or ';'
	q = q.Lt("__key__", datastore.NewKey(c, BuilderKind, master+string(builderIDSep+1), 0, nil))
	return q
}

// Builder is a Buildbot builder that needs to be migrated to LUCI.
type Builder struct {
	Kind           string    `gae:"$kind,Builder"`
	ID             BuilderID `gae:"$id"`
	SchedulingType config.SchedulingType
	OS             config.OS

	IssueID IssueID

	LUCIBuildbucketBucket  string
	LUCIBuildbucketBuilder string

	Migration BuilderMigration

	ExperimentPercentage int
}

// IssueID globally identifies a Monorail issue.
type IssueID struct {
	Hostname string
	Project  string
	ID       int
}

// URL returns issue URL.
func (i *IssueID) URL() string {
	if i.Hostname == "monorail-prod.appspot.com" && i.Project == "chromium" {
		return fmt.Sprintf("https://crbug.com/%d", i.ID)
	}

	return fmt.Sprintf("https://%s/p/%s/issues/detail?id=%d", i.Hostname, i.Project, i.ID)
}

// BuilderID is a combination of a Buildbot master and builder.
type BuilderID struct {
	Master  string // without "master." prefix
	Builder string
}

// String implements fmt.Stringer.
func (b *BuilderID) String() string {
	return b.Master + string(builderIDSep) + b.Builder
}

// Parse parses a builder ID from s. It is the opposite of String().
func (b *BuilderID) Parse(str string) error {
	sep := strings.IndexRune(str, builderIDSep)
	if sep == -1 {
		return errors.Reason("no %q in %q", builderIDSep, str).Err()
	}

	b.Master = str[:sep]
	b.Builder = str[sep+1:]
	return nil
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
	return b.Parse(str)
}
