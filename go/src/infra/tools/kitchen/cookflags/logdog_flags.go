// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"flag"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/logdog/client/butlerlib/streamproto"
	"github.com/luci/luci-go/logdog/common/types"
	"github.com/luci/luci-go/swarming/tasktemplate"
)

// LogDogFlags are the subset of flags which control logdog behavior.
type LogDogFlags struct {
	AnnotationURL          string
	GlobalTags             streamproto.TagMap
	LogDogOnly             bool
	LogDogSendIOKeepAlives bool

	FilePath               string
	ServiceAccountJSONPath string

	// AnnotationAddr is the address of the LogDog annotation stream. It is
	// resolved from the "AnnotationURL" field during "setupAndValidate".
	AnnotationAddr *types.StreamAddr
}

func (p *LogDogFlags) register(fs *flag.FlagSet) {
	fs.StringVar(
		&p.AnnotationURL,
		"logdog-annotation-url",
		"",
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
	return p.AnnotationURL != "" || p.FilePath != ""
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

func (p *LogDogFlags) setupAndValidate(mode CookMode, env environ.Env) error {
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
	if p.AnnotationURL == "" {
		return inputError("-logdog-debug-out-file requires -logdog-annotation-url")
	}

	// Resolve templating parameters.
	var params tasktemplate.Params
	if err := mode.FillTemplateParams(env, &params); err != nil {
		return errors.Annotate(err).Reason("failed to populate template parameters").Err()
	}

	// Parse/resolve annotation URL.
	annotationURL, err := params.Resolve(p.AnnotationURL)
	if err != nil {
		return errors.Annotate(err).Reason("failed to resolve LogDog annotation URL (-logdog-annotation-url)").
			D("value", p.AnnotationURL).
			Err()
	}
	if p.AnnotationAddr, err = types.ParseURL(annotationURL); err != nil {
		return inputError("invalid LogDog annotation URL (-logdog-annotation-url) %q: %s", annotationURL, err)
	}

	return nil
}
