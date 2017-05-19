package step

import (
	"fmt"
	"sort"
	"strings"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/data/stringset"

	"infra/monitoring/messages"
)

var idPrefixes = []string{
	"Device Affinity: ", // Emitted by android recipes.
	"Bot id: ",          // Emitted by perf tests.
}

// Gets the Bot ID a step (probably a step) was executed on.
// TODO(martiniss): Use more structured data.
func getBotID(step *messages.Step) string {
	lines := []string{}
	for _, line := range step.Text {
		line = strings.Replace(line, "<br/>", "<br>", -1)
		split := strings.Split(line, "<br>")
		lines = append(lines, split...)
	}

	for _, line := range lines {
		line = strings.TrimSpace(line)

		for _, prefix := range idPrefixes {
			if len(line) < len(prefix) {
				continue
			}

			if !strings.Contains(line, prefix) {
				continue
			}

			affinity := line[len(prefix)+strings.Index(line, prefix):]
			return strings.TrimSpace(string(affinity))
		}
	}
	return ""
}

type botFailure struct {
	Builder string
	Bots    []string
}

func (p *botFailure) Signature() string {
	return fmt.Sprintf("%s/%s", p.Builder, p.devicesStr())
}

// devicesStr is a string representation of the device affinities which have
// failed.
func (p *botFailure) devicesStr() string {
	sort.Strings(p.Bots)

	return strings.Join(p.Bots, ", ")
}

func (p *botFailure) Kind() string {
	return "bot"
}

func (p *botFailure) Severity() messages.Severity {
	return messages.InfraFailure
}

func (p *botFailure) Title(bses []*messages.BuildStep) string {
	f := bses[0]
	return fmt.Sprintf("bot affinity %s is broken on %s/%s, affecting %d tests", p.devicesStr(), f.Master.Name(), p.Builder, len(bses))
}

// botAnalyzer looks for failures where it look like the bot which ran the
// tests has infrastructure issues. It does this by looking for annotations on
// the step which was run to determine which bots were affected, and by only
// analyzing steps which were infrastructure failures.
func botAnalyzer(ctx context.Context, failures []*messages.BuildStep) ([]messages.ReasonRaw, []error) {
	if len(failures) == 0 {
		return []messages.ReasonRaw{}, nil
	}

	isStepFailure := make(map[string]bool)
	for _, failure := range failures {
		ok, err := failure.Step.IsOK()
		if err != nil {
			continue
		}

		if !ok {
			isStepFailure[failure.Step.Name] = true
		}
	}

	isAffinityFailure := make(map[string]bool)
	deviceWithPassingTests := map[string]bool{}

	for _, step := range failures[0].Build.Steps {
		ID := getBotID(&step)
		if ID == "" {
			continue
		}

		// TODO(martiniss): Remove this. This can be removed once step_metadata is
		// fully implemented on all builders. This is currently blocked on some work
		// in the test runners though, so have to do this hack for now :(
		// See https://crbug.com/680729
		if strings.Contains(step.Name, "[trigger]") {
			continue
		}

		isAffinityFailure[step.Name] = true
		if !isStepFailure[step.Name] {
			deviceWithPassingTests[ID] = true
		}
	}

	results := make([]messages.ReasonRaw, len(failures))
	botWithFailure := []string{}

	devices := stringset.New(1)
	devFailure := &botFailure{
		Builder: failures[0].Build.BuilderName,
		Bots:    []string{},
	}

	for i, f := range failures {
		if f.Step.Name == "Host Info" {
			results[i] = devFailure
			continue
		}

		ID := getBotID(f.Step)

		if ID != "" && !deviceWithPassingTests[ID] {
			botWithFailure = append(botWithFailure, ID)
			// devFailure.Bots might not be fully populated yet, but because of the
			// magic of pointers, this still works.
			results[i] = devFailure
		}
	}

	for _, bot := range botWithFailure {
		devices.Add(bot)
	}
	devFailure.Bots = devices.ToSlice()

	return results, nil
}
