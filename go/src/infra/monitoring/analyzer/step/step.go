package step

import (
	"fmt"

	"infra/monitoring/client"
	"infra/monitoring/messages"
)

// This array MUST be kept in sorted order of "importance". The last analyzer which
// returns a reason for the step failure will be used for the final reason.
// If this is breaking, feel free to re-write; this should be sufficient for now.
var analyzers = []Analyzer{
	&basicAnalyzer{},
	&compileFailureAnalyzer{},
	&testFailureAnalyzer{},
}

// Analyzer reasons about a BuildStep and produces a set of reasons for the
// failure.  Each item in the returned array, if not nil, is the most
// informative reason that we know for the given step.
type Analyzer interface {
	Analyze(client.Reader, []*messages.BuildStep) ([]messages.ReasonRaw, error)
}

// ReasonFinder is a function which finds reasons for a set of build steps.
type ReasonFinder func(Reader client.Reader, failures []*messages.BuildStep) ([]messages.ReasonRaw, error)

// ReasonsForFailures is the default reason finder for package step.
func ReasonsForFailures(Reader client.Reader, failures []*messages.BuildStep) ([]messages.ReasonRaw, error) {
	reasons := make([]messages.ReasonRaw, len(failures))

	for _, fa := range analyzers {
		res, err := fa.Analyze(Reader, failures)
		if err != nil {
			return nil, err
		}

		if res != nil {
			for i := range reasons {
				if res[i] == nil {
					continue
				}

				reasons[i] = res[i]
			}
		}
	}

	return reasons, nil
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

func (b *basicFailure) Title(bses []*messages.BuildStep) string {
	f := bses[0]
	if len(bses) == 1 {
		return fmt.Sprintf("%s failing on %s/%s", f.Step.Name, f.Master.Name(), f.Build.BuilderName)
	}

	return fmt.Sprintf("%s failing on %d builders", f.Step.Name, len(bses))
}

type basicAnalyzer struct{}

func (b *basicAnalyzer) Analyze(reader client.Reader, fs []*messages.BuildStep) ([]messages.ReasonRaw, error) {
	results := make([]messages.ReasonRaw, len(fs))

	for i, f := range fs {
		results[i] = &basicFailure{
			Name: f.Step.Name,
		}
	}

	return results, nil
}
