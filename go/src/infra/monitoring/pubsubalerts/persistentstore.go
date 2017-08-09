package pubsubalerts

import (
	"fmt"
	"log"

	"infra/monitoring/messages"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
)

const (
	storedAlertKind = "StoredAlert"
)

// Load is an implementation of datastore.PropertyLoadSaver that converts
// a slices of builder names to a maps of builder name to bool.
func (sa *StoredAlert) Load(m datastore.PropertyMap) error {
	ps, ok := m["PassingBuilders"]
	if !ok {
		return fmt.Errorf("Couldn't get PassingBuilders from PropertyMap: %+v", m)
	}
	pbs, err := stringSetFromPropertySlice(ps.Slice())
	if err != nil {
		return err
	}

	sa.PassingBuilders = pbs
	delete(m, "PassingBuilders")

	fs, ok := m["FailingBuilders"]
	if !ok {
		return fmt.Errorf("Couldn't get FailingBuilders from PropertyMap: %+v", m)
	}
	fbs, err := stringSetFromPropertySlice(fs.Slice())
	if err != nil {
		return err
	}

	sa.FailingBuilders = fbs
	delete(m, "FailingBuilders")

	log.Printf("pbs: %v, fbs: %v", pbs, fbs)

	return datastore.GetPLS(sa).Load(m)
}

// Save is an implementation of datstore.PropertyLoadSaver that converts
// maps of builder names to bool to slices of builder names.
func (sa *StoredAlert) Save(withMeta bool) (datastore.PropertyMap, error) {
	props, err := datastore.GetPLS(sa).Save(withMeta)
	if err != nil {
		return nil, err
	}

	props["FailingBuilders"] = sa.FailingBuilders.toPropertySlice()
	props["PassingBuilders"] = sa.PassingBuilders.toPropertySlice()

	return props, nil
}

// PersistentAlertStore implements the AlertStore interface with in-memory storage.
// Use this only for testing or command-line utility debugging.
type PersistentAlertStore struct {
}

// NewAlertStore returns a new instance of a persitent alert store
// suitable for production use.
func NewAlertStore() *PersistentAlertStore {
	return &PersistentAlertStore{}
}

// StoreAlert stores the alert in the datastore.
func (s *PersistentAlertStore) StoreAlert(ctx context.Context, alert *StoredAlert) error {
	return datastore.Put(ctx, alert)
}

// NewAlert creates a new StoredAlert for a given BuildStep.
func (s *PersistentAlertStore) NewAlert(ctx context.Context, step *messages.BuildStep) (*StoredAlert, error) {
	sa := &StoredAlert{
		Master:          step.Master.Name(),
		Signature:       alertSignature(step.Step),
		Status:          StatusActive,
		FailingBuilders: stringSet{step.Build.BuilderName: {}},
		PassingBuilders: stringSet{},
		FailingBuilds:   []StoredBuild{storedBuild(step.Build)},
	}

	err := s.StoreAlert(ctx, sa)
	if err != nil {
		return nil, err
	}

	return sa, nil
}

// ActiveAlertForSignature returns the currently active alert matching the signature,
// if any is currently active.
func (s *PersistentAlertStore) ActiveAlertForSignature(ctx context.Context, sig string) (*StoredAlert, error) {
	q := datastore.NewQuery(storedAlertKind).
		Eq("Status", StatusActive).
		Eq("Signature", sig).
		Limit(2)

	ret := []*StoredAlert{}
	err := datastore.GetAll(ctx, q, &ret)

	if len(ret) > 1 {
		return nil, fmt.Errorf("Multiple active alerts for signature %q", sig)
	} else if len(ret) > 0 {
		return ret[0], err
	}
	return nil, nil
}

// ActiveAlertsForBuilder returns any active alerts associate with the builder.
func (s *PersistentAlertStore) ActiveAlertsForBuilder(ctx context.Context, masterName string, builderName string) ([]*StoredAlert, error) {
	q := datastore.NewQuery(storedAlertKind).
		Eq("Status", StatusActive).
		Eq("Master", masterName)

	if builderName != "" {
		q = q.Eq("FailingBuilders", builderName)
	}

	ret := []*StoredAlert{}
	err := datastore.GetAll(ctx, q, &ret)

	return ret, err
}
