// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"flag"

	"go.chromium.org/luci/logdog/client/butlerlib/streamproto"
	"go.chromium.org/luci/logdog/common/types"
)

// LogDogFlags are the subset of flags which control logdog behavior.
type LogDogFlags struct {
	AnnotationURL types.StreamAddr   `json:"annotation_url"`
	GlobalTags    streamproto.TagMap `json:"global_tags"`

	FilePath string `json:"file_path"`
}

func (p *LogDogFlags) register(fs *flag.FlagSet) {
	fs.Var(
		&p.AnnotationURL,
		"logdog-annotation-url",
		"The URL of the LogDog annotation stream to use (logdog://host/project/prefix/+/name). The LogDog "+
			"project and prefix will be extracted from this URL.")
	fs.StringVar(
		&p.FilePath,
		"logdog-debug-out-file",
		"",
		"If specified, write all generated logs to this path instead of sending them.")
	fs.Var(
		&p.GlobalTags,
		"logdog-tag",
		"Specify key[=value] tags to be applied to all log streams. Individual streams may override. Can "+
			"be specified multiple times.")
}

func (p *LogDogFlags) validate() error {
	if p.AnnotationURL.IsZero() {
		return inputError("-logdog-annotation-url is required")
	}
	return nil
}

// Dump returns a []string command line argument which matches this LogDogFlags.
func (p *LogDogFlags) Dump() []string {
	ret := flagDumper{}
	if !p.AnnotationURL.IsZero() {
		ret = append(ret, "-logdog-annotation-url", p.AnnotationURL.String())
	}
	ret.stringMap("logdog-tag", p.GlobalTags)
	ret.str("logdog-debug-out-file", p.FilePath)
	return ret
}
