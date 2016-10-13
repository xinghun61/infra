package pubsubalerts

import (
	"sort"
	"testing"

	helper "infra/monitoring/analyzer/test"
	"infra/monitoring/messages"

	. "github.com/smartystreets/goconvey/convey"
)

func sortedKeys(s map[string]*messages.Build) []string {
	keys := []string{}
	for k := range s {
		keys = append(keys, k)
	}

	sort.Strings(keys)
	return keys
}

func TestHandleBuild(t *testing.T) {
	Convey("should return an error on nil build", t, func() {
		b := &BuildHandler{Store: NewInMemAlertStore()}
		err := b.HandleBuild(nil)
		So(err, ShouldNotEqual, nil)
	})

	Convey("build with one newly failing step", t, func() {
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake step").Results(0).BuilderFaker.
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake step").Results(2).BuilderFaker

		inMemStore := NewInMemAlertStore()
		b := &BuildHandler{Store: inMemStore}

		for _, buildKey := range sortedKeys(bf.Builds) {
			err := b.HandleBuild(bf.Builds[buildKey])
			So(err, ShouldEqual, nil)
		}

		alerts := inMemStore.ActiveAlertsForBuilder("fake.builder")
		So(len(alerts), ShouldEqual, 1)

		So(len(alerts[0].FailingBuilds), ShouldEqual, 1)

		expectedAlerts := []*StoredAlert{
			{
				Key:             "0",
				Status:          StatusActive,
				Signature:       "fake step",
				FailingBuilders: map[string]bool{"fake.builder": true},
				FailingBuilds:   []*messages.Build{bf.Builds["fake.master/fake.builder/1"]},
				PassingBuilders: map[string]bool{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with one newly passing step", t, func() {
		inMemStore := NewInMemAlertStore()
		b := &BuildHandler{Store: inMemStore}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake step").Results(2).BuilderFaker.
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake step").Results(0).BuilderFaker

		for _, buildKey := range sortedKeys(bf.Builds) {
			err := b.HandleBuild(bf.Builds[buildKey])
			So(err, ShouldEqual, nil)
		}

		alerts := inMemStore.ActiveAlertsForBuilder("fake.builder")
		So(len(alerts), ShouldEqual, 0)
	})

	Convey("build with two failing steps", t, func() {
		inMemStore := NewInMemAlertStore()
		b := &BuildHandler{Store: inMemStore}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []*messages.Build{}

		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, build)
		}

		So(len(inMemStore.StoredAlerts), ShouldEqual, 2)

		alerts := inMemStore.ActiveAlertsForBuilder("fake.builder")
		So(len(alerts), ShouldEqual, 2)

		expectedAlerts := []*StoredAlert{
			{
				Key:             "0",
				Status:          StatusActive,
				Signature:       "fake_step",
				FailingBuilders: map[string]bool{"fake.builder": true},
				FailingBuilds:   failingBuilds,
				PassingBuilders: map[string]bool{},
			},
			{
				Key:             "1",
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: map[string]bool{"fake.builder": true},
				FailingBuilds:   failingBuilds,
				PassingBuilders: map[string]bool{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with two failing steps, followed by a build with one failing step", t, func() {
		inMemStore := NewInMemAlertStore()
		b := &BuildHandler{Store: inMemStore}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker.
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake_step").Results(0).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []*messages.Build{}
		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, build)
		}

		So(len(inMemStore.StoredAlerts), ShouldEqual, 2)

		alerts := inMemStore.ActiveAlertsForBuilder("fake.builder")
		So(len(alerts), ShouldEqual, 1)

		expectedAlerts := []*StoredAlert{
			{
				Key:             "1",
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: map[string]bool{"fake.builder": true},
				FailingBuilds:   failingBuilds,
				PassingBuilders: map[string]bool{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with two failing steps, followed by a build with one failing step, delivered out of order", t, func() {
		inMemStore := NewInMemAlertStore()
		b := &BuildHandler{Store: inMemStore}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake_step").Results(0).BuildFaker.
			Step("other step").Results(2).BuilderFaker.
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []*messages.Build{}
		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, build)
		}

		So(len(inMemStore.StoredAlerts), ShouldEqual, 2)

		alerts := inMemStore.ActiveAlertsForBuilder("fake.builder")
		So(len(alerts), ShouldEqual, 1)

		expectedAlerts := []*StoredAlert{
			{
				Key:             "1",
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: map[string]bool{"fake.builder": true},
				FailingBuilds:   failingBuilds,
				PassingBuilders: map[string]bool{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with one failing step, followed by a build with two failing steps, delivered out of order", t, func() {
		inMemStore := NewInMemAlertStore()
		b := &BuildHandler{Store: inMemStore}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker.
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(0).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []*messages.Build{}
		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, build)
		}

		So(len(inMemStore.StoredAlerts), ShouldEqual, 2)

		alerts := inMemStore.ActiveAlertsForBuilder("fake.builder")
		So(len(alerts), ShouldEqual, 2)

		expectedAlerts := []*StoredAlert{
			{
				Key:             "1",
				Status:          StatusActive,
				Signature:       "fake_step",
				FailingBuilders: map[string]bool{"fake.builder": true},
				FailingBuilds:   failingBuilds[1:],
				PassingBuilders: map[string]bool{},
			},
			{
				Key:             "0",
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: map[string]bool{"fake.builder": true},
				FailingBuilds:   failingBuilds,
				PassingBuilders: map[string]bool{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})
}
