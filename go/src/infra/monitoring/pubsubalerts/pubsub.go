package pubsubalerts

// Package pubsubalerts is a Cloud PubSub client that updates a set of
// alerts based on incoming build events.

import (
	"fmt"
	"log"
	"net/url"

	"infra/monitoring/messages"
)

// AlertStatus is an enum type to denote the status of an alert.
type AlertStatus string

const (
	// Step result values.
	resOK           = float64(1)
	resInfraFailure = float64(4)

	// StatusActive indicates an active alert.
	StatusActive = "active"
	// StatusInactive indicates an inactive alert.
	StatusInactive = "inactive"
)

// StoredAlert represents stored alert data.
type StoredAlert struct {
	// The alert key. It is an opaque string, unique to an instance.
	Key string
	// The alert signature is unique to a particular combination of failure
	// properties but is also otherwise opaque to users.
	Signature string
	// Status of the alert.
	Status AlertStatus
	// FailingBuilders is a map of builder names for currently failing builders.
	FailingBuilders map[string]bool
	// PassingBuilders is a map of builder names for builders that previously were failing but are now passing.
	PassingBuilders map[string]bool
	// FailingBuilds is an array of builds that failed over the lifetime of this alert.
	FailingBuilds []*messages.Build
	// PassingBuilds is an array of builds that started passing since the start of this alert.
	PassingBuilds []*messages.Build
}

// AlertStore is expected to provide acces to a shared, persistent set of
// alerts.
type AlertStore interface {
	ActiveAlertForSignature(sig string) *StoredAlert
	ActiveAlertsForBuilder(builderName string) []*StoredAlert
	NewAlert(step *messages.BuildStep) *StoredAlert
	StoreAlert(sig string, alert *StoredAlert)
}

// The same signature can appear in failures on multiple builders.
// Examples would include: a single failing step name, multiple failing step
// names concatenated in lexical order, single failing step concatenated
// with mutltiple failing test names concatenated in lexical order.
func alertSignature(failingStep *messages.Step) string {
	// TODO:
	// - include test names, canonicalized if it's a test.
	// - include multiple failing steps (probably have to change the signature
	//   of this func to do that).

	return fmt.Sprintf("%s", failingStep.Name)
}

// analyzeSteps returns alertable failing and passing build steps for a given build.
// TODO: filter for only the alertable steps.
func analyzeSteps(b *messages.Build) ([]*messages.BuildStep, []*messages.BuildStep) {
	failures := []*messages.BuildStep{}
	passes := []*messages.BuildStep{}

	masterURL, err := url.Parse(b.Master)

	// TODO: handle err
	if err != nil {
		log.Printf("error parsing master url: %v", err)
	}

	for _, s := range b.Steps {
		// Done so references created later inside this loop body don't all point to
		// the last element in b.Steps.
		s := s

		if !s.IsFinished || len(s.Results) == 0 {
			continue
		}
		// Because Results in the json data is a homogeneous array, the unmarshaler
		// doesn't have any type information to assert about it. We have to do
		// some ugly runtime type assertion ourselves.
		if r, ok := s.Results[0].(float64); ok {
			if r <= resOK {
				// This 0/1 check seems to be a convention or heuristic. A 0 or 1
				// result is apparently "ok", accoring to the original python code.
				passes = append(passes, &messages.BuildStep{
					Master: &messages.MasterLocation{URL: *masterURL},
					Build:  b,
					Step:   &s,
				})
				continue
			}
		} else {
			log.Printf("Couldn't unmarshal first step result into a float64: %v", s.Results[0])
		}

		// We have a failure of some kind, so queue it up to check later.

		failures = append(failures, &messages.BuildStep{
			Master: &messages.MasterLocation{URL: *masterURL},
			Build:  b,
			Step:   &s,
		})
	}

	return failures, passes
}

// BuildHandler associates an AlertStore implementation with the HandleBuild function.
type BuildHandler struct {
	Store AlertStore
}

func buildOrder(a, b *messages.Build) bool {
	// TODO: something more robust. Master restarts break this comparison.
	// Other properties to compare: time stamps, revision ranges.
	return a.Number < b.Number
}

// HandleBuild is the main entry point for this analyzer. It is stateful via
// the BuildHandler instance's Store field. It is intended to be safe for
// build events delivered out of order. That is, failing build events that are
// delivered after passing build events in the actual build timeline will not
// generate new alerts.
func (b *BuildHandler) HandleBuild(build *messages.Build) error {
	if build == nil {
		return fmt.Errorf("build parameter was nil")
	}

	failures, passes := analyzeSteps(build)

	log.Printf("%d failures, %d passes in %s/%d:\n", len(failures), len(passes), build.BuilderName, build.Number)
	// Either create a new alert or attach this failure to an existing alert
	// that matches this signature.
	// TODO: Get/filter reasons for the failure.
	for _, failure := range failures {
		sig := alertSignature(failure.Step)

		if alert := b.Store.ActiveAlertForSignature(sig); alert != nil {
			// Now check to see if the failure has been supersceded by an ok build
			// that arived prior to the arrival of this build event, but occurred
			// after it logically (e.g. a late build failure event for currently
			// passing build).
			superceeded := false
			for _, okb := range alert.PassingBuilds {
				if okb.BuilderName == build.BuilderName && buildOrder(build, okb) {
					log.Printf("Discarding failure in %s/%d because it's passing in %s/%d.", build.BuilderName, build.Number, okb.BuilderName, okb.Number)
					superceeded = true
				}
			}
			log.Printf("Adding %s to %s\n", failure.Build.BuilderName, sig)
			alert.FailingBuilders[failure.Build.BuilderName] = true
			alert.FailingBuilds = append(alert.FailingBuilds, failure.Build)
			if !superceeded {
				alert.Status = StatusActive
			}
			b.Store.StoreAlert(sig, alert)
		} else {
			log.Printf("Creating a new alert for %s on %s\n", failure.Build.BuilderName, sig)
			alert := b.Store.NewAlert(failure)
			b.Store.StoreAlert(sig, alert)
		}
	}

	// Now remove the builder from any alerts on steps that passed in this build.
	// Clear out alerts that no longer apply.
	for _, alert := range b.Store.ActiveAlertsForBuilder(build.BuilderName) {
		log.Printf("Checking if %s is still active for alert on %s\n", build.BuilderName, alert.Signature)
		for _, passingStep := range passes {
			superceeded := false
			if alert.Signature == alertSignature(passingStep.Step) {
				// Make sure this isn't an old successful step that has been superceeded
				// by a newer failure that arrived prior to this build event.
				for _, failedBuild := range alert.FailingBuilds {
					if buildOrder(build, failedBuild) {
						log.Printf("%d is passing, but failing build %d occurred after it logically.\n", build.Number, failedBuild.Number)
						superceeded = true
					}
				}
				if !superceeded {
					log.Printf("Removing %s from failing builders on %s.\n", build.BuilderName, alert.Signature)
					delete(alert.FailingBuilders, build.BuilderName)
					alert.PassingBuilders[build.BuilderName] = true
					if len(alert.FailingBuilders) == 0 {
						alert.Status = StatusInactive
						log.Printf("Deactivating alert: %s\n", alert.Signature)
					}
				}
				alert.PassingBuilds = append(alert.PassingBuilds, passingStep.Build)
				b.Store.StoreAlert(alert.Signature, alert)
			}
		}
	}

	return nil
}
