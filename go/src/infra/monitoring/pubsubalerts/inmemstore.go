package pubsubalerts

import (
	"sort"

	"infra/monitoring/messages"

	"golang.org/x/net/context"
)

// InMemAlertStore implements the AlertStore interface with in-memory storage.
// Use this only for testing or command-line utility debugging.
type InMemAlertStore struct {
	StoredAlerts map[string]*StoredAlert
	nextID       int64
}

// NewInMemAlertStore returns a new instance of an in-memory alert store
// suitable for unit tests or command line utilities.
func NewInMemAlertStore() *InMemAlertStore {
	return &InMemAlertStore{map[string]*StoredAlert{}, 0}
}

// StoreAlert stores the alert in memory.
func (s *InMemAlertStore) StoreAlert(ctx context.Context, alert *StoredAlert) error {
	if alert.ID == 0 {
		alert.ID = s.newID()
	}
	s.StoredAlerts[alert.Signature] = alert
	return nil
}

func (s *InMemAlertStore) newID() int64 {
	s.nextID++
	return s.nextID
}

// NewAlert creates a new StoredAlert for a given BuildStep.
func (s *InMemAlertStore) NewAlert(ctx context.Context, step *messages.BuildStep) (*StoredAlert, error) {
	return &StoredAlert{
		Master:          step.Master.Name(),
		Signature:       alertSignature(step.Step),
		Status:          StatusActive,
		FailingBuilders: stringSet{step.Build.BuilderName: {}},
		PassingBuilders: stringSet{},
		FailingBuilds:   []StoredBuild{storedBuild(step.Build)},
	}, nil
}

// ActiveAlertForSignature returns the currently active alert matching the signature,
// if any is currently active.
func (s *InMemAlertStore) ActiveAlertForSignature(ctx context.Context, sig string) (*StoredAlert, error) {
	if alert, ok := s.StoredAlerts[sig]; ok && alert.Status == StatusActive {
		return alert, nil
	}
	return nil, nil
}

// ActiveAlertsForBuilder returns any active alerts associate with the builder.
func (s *InMemAlertStore) ActiveAlertsForBuilder(ctx context.Context, masterName, builderName string) ([]*StoredAlert, error) {
	ret := []*StoredAlert{}
	keys := []string{}
	for key := range s.StoredAlerts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		alert := s.StoredAlerts[key]
		if _, ok := alert.FailingBuilders[builderName]; ok {
			ret = append(ret, alert)
		}
	}
	sort.Sort(byID(ret))
	return ret, nil
}

type byID []*StoredAlert

func (a byID) Len() int           { return len(a) }
func (a byID) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a byID) Less(i, j int) bool { return a[i].ID < a[j].ID }
