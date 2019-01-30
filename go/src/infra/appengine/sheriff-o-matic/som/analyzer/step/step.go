package step

import (
	"fmt"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"

	"infra/appengine/sheriff-o-matic/som/client"
	"infra/monitoring/messages"
)

// DefaultStepAnalyzers returns a set of default step analyzers.
func DefaultStepAnalyzers(logReader client.LogReader, findIt client.FindIt, testResults client.TestResults) BuildStepAnalyzers {
	return []BuildStepAnalyzer{
		&basicStepAnalyzer{},
		&compileFailureAnalyzer{
			logReader: logReader,
		},
		&testFailureAnalyzer{
			findit: findIt,
			trc:    testResults,
		},
		&botAnalyzer{},
	}
}

// BuildStepAnalyzer reasons about a BuildStep and produces a set of reasons for the
// failure.  Each item in the returned array, if not nil, is the most
// informative reason that we know for the given step.
// If the analyzer returns errors, the reasons provided by it are only
// considered invalid for the build steps which the analyzer had errors
// processing.
type BuildStepAnalyzer interface {
	Analyze(ctx context.Context, failures []*messages.BuildStep, tree string) ([]messages.ReasonRaw, []error)
}

// ReasonFinder is a function which finds reasons for a set of build steps.
type ReasonFinder func(ctx context.Context, failures []*messages.BuildStep, tree string) []messages.ReasonRaw

// BuildStepAnalyzers is an ordered list of StepAnalyzers.
type BuildStepAnalyzers []BuildStepAnalyzer

// ReasonsForFailures is the default reason finder for package step.
func (analyzers BuildStepAnalyzers) ReasonsForFailures(ctx context.Context, failures []*messages.BuildStep, tree string) []messages.ReasonRaw {
	reasons := make([]messages.ReasonRaw, len(failures))

	for _, fa := range analyzers {
		res, errs := fa.Analyze(ctx, failures, tree)
		if errs != nil {
			logging.Errorf(ctx, "Got errors while analyzing with %v: %s", fa, errs)
		}

		if res != nil {
			for i := range reasons {
				if res[i] == nil || (errs != nil && errs[i] != nil) {
					continue
				}
				reasons[i] = res[i]
			}
		}
	}

	return reasons
}

type basicFailure struct {
	Name string `json:"name"`
}

func (b *basicFailure) Signature() string {
	return b.Name
}

func (b *basicFailure) Kind() string {
	return "basic"
}

func (b *basicFailure) Severity() messages.Severity {
	return messages.NoSeverity
}

func (b *basicFailure) Title(bses []*messages.BuildStep) string {
	f := bses[0]
	if len(bses) == 1 {
		return fmt.Sprintf("%s failing on %s/%s", f.Step.Name, f.Master.Name(), f.Build.BuilderName)
	}

	return fmt.Sprintf("%s failing on multiple builders", f.Step.Name)
}

type basicStepAnalyzer struct{}

func (b *basicStepAnalyzer) Analyze(ctx context.Context, fs []*messages.BuildStep, tree string) ([]messages.ReasonRaw, []error) {
	results := make([]messages.ReasonRaw, len(fs))

	for i, f := range fs {
		results[i] = &basicFailure{
			Name: f.Step.Name,
		}
	}

	return results, nil
}
