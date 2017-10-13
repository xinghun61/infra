// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"io/ioutil"
	"net/url"
	"os"
	"strings"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto"
)

var defPath = flag.String(
	"path",
	"",
	"path to the file with text proto Template message, see template.proto")

var queryEscape = flag.Bool(
	"query-escape",
	false,
	"escape the URL as a query string parameter")

func (p Priority) Label() string {
	if p == 0 {
		return ""
	}
	return "Pri-" + strings.TrimPrefix(p.String(), "P")
}

func (t Type) Label() string {
	if t == 0 {
		return ""
	}
	return "Type-" + t.String()
}

func cleanStrings(slice []string) []string {
	// keep it simple
	clean := make([]string, 0, len(slice))
	for _, s := range slice {
		s = strings.TrimSpace(s)
		if s != "" {
			clean = append(clean, s)
		}
	}
	return clean
}

func run() error {
	flag.Parse()
	if len(flag.Args()) > 0 {
		return fmt.Errorf("unexpected args: %q", flag.Args())
	}

	contents, err := ioutil.ReadFile(*defPath)
	if err != nil {
		return errors.Annotate(err, "failed to read template file").Err()
	}

	var template Template
	if err := proto.UnmarshalTextML(string(contents), &template); err != nil {
		return errors.Annotate(err, "failed to parse template file").Err()
	}
	template.Labels = append(template.Labels, template.Pri.Label(), template.Type.Label())

	params := url.Values{}
	params.Set("summary", template.Summary)
	params.Set("comment", template.Description)
	params.Set("cc", strings.Join(cleanStrings(template.Cc), ","))
	params.Set("components", strings.Join(cleanStrings(template.Components), ","))
	params.Set("labels", strings.Join(cleanStrings(template.Labels), ","))
	ret := "https://bugs.chromium.org/p/chromium/issues/entry?" + params.Encode()
	if *queryEscape {
		ret = url.QueryEscape(ret)
	}
	fmt.Println(ret)
	return nil
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
