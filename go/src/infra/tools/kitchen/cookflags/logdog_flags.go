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
	AnnotationURL          types.StreamAddr   `json:"annotation_url"`
	GlobalTags             streamproto.TagMap `json:"global_tags"`
	LogDogOnly             bool               `json:"logdog_only"`
	LogDogSendIOKeepAlives bool               `json:"send_io_keepalives"`

	FilePath               string `json:"file_path"`
	ServiceAccountJSONPath string `json:"service_account_json_path"`
}

func (p *LogDogFlags) register(fs *flag.FlagSet) {
	fs.Var(
		&p.AnnotationURL,
		"logdog-annotation-url",
		"The URL of the LogDog annotation stream to use (logdog://host/project/prefix/+/name). The LogDog "+
			"project and prefix will be extracted from this URL. This can include Swarmbucket template parameters.")
	fs.BoolVar(
		&p.LogDogOnly,
		"logdog-only",
		false,
		"Send all output and annotations through LogDog. Implied by swarming mode.")
	fs.BoolVar(
		&p.LogDogSendIOKeepAlives,
		"logdog-send-io-keepalives",
		false,
		"When in LogDog-only mode (-logdog-only), send I/O keepalives.")
	fs.StringVar(
		&p.FilePath,
		"logdog-debug-out-file",
		"",
		"If specified, write all generated logs to this path instead of sending them.")
	fs.StringVar(
		&p.ServiceAccountJSONPath,
		"logdog-service-account-json-path",
		"",
		"If specified, use the service account JSON file at this path. Otherwise, autodetect.")
	fs.Var(
		&p.GlobalTags,
		"logdog-tag",
		"Specify key[=value] tags to be applied to all log streams. Individual streams may override. Can "+
			"be specified multiple times.")
}

// Active returns true iff LogDog is active for this run.
func (p *LogDogFlags) Active() bool {
	return !p.AnnotationURL.IsZero() || p.FilePath != ""
}

// ShouldEmitAnnotations returns true if the cook command should emit additional
// annotations.
//
// If we're streaming solely to LogDog, it makes no sense to emit extra
// annotations, since nothing will consume them; however, if we're tee-ing, we
// will continue to emit additional annotations in case something is looking
// at the tee'd output.
//
// Note that this could create an incongruity between the LogDog-emitted
// annotations and the annotations in the STDOUT stream.
func (p *LogDogFlags) ShouldEmitAnnotations() bool {
	return !(p.LogDogOnly && p.Active())
}

func (p *LogDogFlags) setupAndValidate(mode CookMode) error {
	// Adjust some flags according to the chosen mode.
	if mode.onlyLogDog() {
		p.LogDogOnly = true
	}

	if !p.Active() {
		if p.LogDogOnly {
			return inputError("LogDog flag (-logdog-only) requires -logdog-annotation-url or -logdog-debug-out-file")
		}
		return nil
	}
	if p.AnnotationURL.IsZero() {
		return inputError("-logdog-debug-out-file requires -logdog-annotation-url")
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
	ret.boolean("logdog-only", p.LogDogOnly)
	ret.boolean("logdog-send-io-keepalives", p.LogDogSendIOKeepAlives)
	ret.str("logdog-debug-out-file", p.FilePath)
	ret.str("logdog-service-account-json-path", p.ServiceAccountJSONPath)
	return ret
}
