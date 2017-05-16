// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package migration

import (
	"fmt"
	"strings"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/errors"
)

type builder struct {
	Kind                   string    `gae:"$kind,Builder"`
	ID                     builderID `gae:"$id"`
	SchedulingType         schedulingType
	Public                 bool
	IssueID                int
	LUCIBuildbucketBucket  string
	LUCIBuildbucketBuilder string
	OS                     os
}

type builderID struct {
	Master  string // without "master." prefix
	Builder string
}

func (b *builderID) String() string {
	return b.Master + ":" + b.Builder
}

func (b *builderID) ToProperty() (datastore.Property, error) {
	return datastore.MkProperty(b.String()), nil
}

func (b *builderID) FromProperty(p datastore.Property) error {
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

type schedulingType int

const (
	tryScheduling schedulingType = iota
	continuousScheduling
)

type os int

const (
	unknownOS os = iota
	linux
	mac
	windows
	android
	iOS
)

// String returns a valid value for OS monorail label.
func (os os) String() string {
	switch os {
	case unknownOS:
		return ""
	case linux:
		return "Linux"
	case mac:
		return "Mac"
	case windows:
		return "Windows"
	case android:
		return "Android"
	case iOS:
		return "iOS"
	default:
		return fmt.Sprintf("invalid os %d", os)
	}
}
