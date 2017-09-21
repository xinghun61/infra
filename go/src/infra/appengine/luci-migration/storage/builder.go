// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package storage

import (
	"fmt"
	"strings"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"

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

	IssueID                 IssueID
	IssueDescriptionVersion int

	LUCIBuildbucketBucket string

	Migration BuilderMigration

	ExperimentPercentage int

	MostRecentNotification Notification

	Expando datastore.PropertyMap `gae:",extra"` // future or deprecated fields
}

// Notification contains info about a notification sent about a status change.
type Notification struct {
	Time     time.Time // zero, if never sent
	Status   MigrationStatus
	TaskName string
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
