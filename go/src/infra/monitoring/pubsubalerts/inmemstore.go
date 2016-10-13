package pubsubalerts

import (
	"fmt"
	"infra/monitoring/messages"
	"sort"
)

// InMemAlertStore implements the AlertStore interface with in-memory storage.
// Use this only for testing or command-line utility debugging.
type InMemAlertStore struct {
	StoredAlerts map[string]*StoredAlert
	nextID       int
}

// NewInMemAlertStore returns a new instance of an in-memory alert store
// suitable for unit tests or command line utilities.
func NewInMemAlertStore() *InMemAlertStore {
	return &InMemAlertStore{map[string]*StoredAlert{}, 0}
}

// StoreAlert stores the alert in memory.
func (s *InMemAlertStore) StoreAlert(sig string, alert *StoredAlert) {
	s.StoredAlerts[sig] = alert
}

func (s *InMemAlertStore) newID() string {
	ret := fmt.Sprintf("%d", s.nextID)
	s.nextID++
	return ret
}

// NewAlert creates a new StoredAlert for a given BuildStep.
func (s *InMemAlertStore) NewAlert(step *messages.BuildStep) *StoredAlert {
	return &StoredAlert{
		Key:             s.newID(),
		Signature:       alertSignature(step.Step),
		Status:          StatusActive,
		FailingBuilders: map[string]bool{step.Build.BuilderName: true},
		PassingBuilders: map[string]bool{},
		FailingBuilds:   []*messages.Build{step.Build},
	}
}

// ActiveAlertForSignature returns the currently active alert matching the signature,
// if any is currently active.
func (s *InMemAlertStore) ActiveAlertForSignature(sig string) *StoredAlert {
	if alert, ok := s.StoredAlerts[sig]; ok && alert.Status == StatusActive {
		return alert
	}
	return nil
}

// ActiveAlertsForBuilder returns any active alerts associate with the builder.
func (s *InMemAlertStore) ActiveAlertsForBuilder(builderName string) []*StoredAlert {
	ret := []*StoredAlert{}
	keys := []string{}
	for key := range s.StoredAlerts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		alert := s.StoredAlerts[key]
		if alert.FailingBuilders[builderName] {
			ret = append(ret, alert)
		}
	}
	return ret
}
