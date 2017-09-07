package test

import (
	"fmt"
	"net/url"

	"infra/monitoring/messages"
)

func urlParse(s string) *url.URL {
	p, err := url.Parse(s)
	if err != nil {
		panic(err)
	}
	return p
}

/*

Use these helpers like so:

b := newBuilderFaker("some builder")
b.build(buildNum).revisionCP("refs/heads/master@{123}")
b.build(buildNum).step("stepname").result(0)
b.build(buildNum).step("other stepname").result(0)
b.build(buildNum).revisionCP("refs/heads/master@{456}")
b.build(buildNum+1).step("stepname").result(0)
b.build(buildNum+1).step("other stepname").result(2)

Or by chaining them together inline. The fakers contain references to their
parent fakers if you need to back out of the chain from step to build to
builder.

After construction, b.Builds contains a map[string]*messages.Build that you
can use in either alert contents or in analyzer input for testing.
*/

// BuilderFaker helps build example build log messages for testing purposes.
type BuilderFaker struct {
	MasterName, BuilderName string
	Builds                  map[string]*messages.Build
}

// NewBuilderFaker returns a new BuilderFaker.
func NewBuilderFaker(masterName, builderName string) *BuilderFaker {
	return &BuilderFaker{masterName, builderName, map[string]*messages.Build{}}
}

// Build constructs a new BuildFaker for buildNum in f if it doesn't already
// exist, and returns one either way.
func (f *BuilderFaker) Build(buildNum int) *BuildFaker {
	ret := &BuildFaker{}
	path := fmt.Sprintf("%s/%s/%d", f.MasterName, f.BuilderName, buildNum)
	b, ok := f.Builds[path]
	if !ok {
		b = &messages.Build{Number: int64(buildNum)}
		f.Builds[path] = b
	}
	b.Master = f.MasterName
	b.BuilderName = f.BuilderName
	ret.BuilderFaker = f
	ret.Build = b
	return ret
}

// GetBuilds returns an array of builds.
func (f *BuilderFaker) GetBuilds() []*messages.Build {
	ret := []*messages.Build{}
	for _, b := range f.Builds {
		ret = append(ret, b)
	}
	return ret
}

// StepsAtFault is useful to create a list of build steps, which can be inserted
// into a messages.BuildFailure, when creating tests.
func StepsAtFault(f *BuilderFaker, builds []int, stepNames []string) []messages.BuildStep {
	buildSteps := []messages.BuildStep(nil)

	for i, build := range builds {
		stepName := stepNames[i]
		path := fmt.Sprintf("%s/%s/%d", f.MasterName, f.BuilderName, build)
		found := false
		for _, step := range f.Builds[path].Steps {
			step := step
			if step.Name == stepName {
				buildSteps = append(buildSteps, messages.BuildStep{
					Step:   &step,
					Master: &messages.MasterLocation{URL: *urlParse(fmt.Sprintf("https://build.chromium.org/p/%s", f.MasterName))},
					Build:  f.Builds[path],
				})
				found = true
				break
			}
		}
		if !found {
			panic(fmt.Sprintf("bad test data. %q not found in %#v", stepName, f.Builds[path].Steps))
		}
	}

	return buildSteps
}

// BuildFaker helps construct individual build records.
type BuildFaker struct {
	Build        *messages.Build
	BuilderFaker *BuilderFaker
}

// Times adds EpochTimes to the the build's Times field.
func (f *BuildFaker) Times(time ...int) *BuildFaker {
	for _, t := range time {
		f.Build.Times = append(f.Build.Times, messages.EpochTime(t))
	}
	return f
}

// IncludeChanges adds Change records to the Build with fake commit comments
// referencing positions in Cr-Commit-Position headers.
func (f *BuildFaker) IncludeChanges(URL string, positions ...string) *BuildFaker {
	for _, pos := range positions {
		revision := "unknown"
		for i, c := range pos {
			if c == '#' {
				revision = pos[i+1 : len(pos)-1]
			}

		}
		change := messages.Change{
			Repository: URL,
			Revision:   revision,
		}
		change.Comments = fmt.Sprintf("some change comment\n\nCr-Commit-Position: %s\n\n", pos)
		f.Build.SourceStamp.Changes = append(f.Build.SourceStamp.Changes, change)
	}
	return f
}

// Step creates a new StepFaker for stepName in the Build, or returns an existing
// StepFaker if one with that name already exists.
func (f *BuildFaker) Step(stepName string) *StepFaker {
	for _, step := range f.Build.Steps {
		if step.Name == stepName {
			return &StepFaker{&step, f, f.BuilderFaker}
		}
	}
	newStep := messages.Step{Name: stepName, IsFinished: true, Results: []interface{}{}}
	f.Build.Steps = append(f.Build.Steps, newStep)
	return &StepFaker{&newStep, f, f.BuilderFaker}
}

// StepFaker helps construct example build step records for testing purpposes.
type StepFaker struct {
	Step         *messages.Step
	BuildFaker   *BuildFaker
	BuilderFaker *BuilderFaker
}

// Results sets the step's numerical result codes.
func (f *StepFaker) Results(result ...int) *StepFaker {
	for _, res := range result {
		f.Step.Results = append(f.Step.Results, float64(res))
	}
	// Fugly. In hindsight messages.Builder and friends should have used
	// pointers for member structs.
	for i, s := range f.BuildFaker.Build.Steps {
		if s.Name == f.Step.Name {
			f.BuildFaker.Build.Steps[i] = *f.Step
		}
	}
	return f
}

// Times sets the step's times.
func (f *StepFaker) Times(time ...int) *StepFaker {
	for _, t := range time {
		f.Step.Times = append(f.Step.Times, messages.EpochTime(t))
	}
	// Fugly. In hindsight messages.Builder and friends should have used
	// pointers for member structs.
	for i, s := range f.BuildFaker.Build.Steps {
		if s.Name == f.Step.Name {
			f.BuildFaker.Build.Steps[i] = *f.Step
		}
	}
	return f
}
