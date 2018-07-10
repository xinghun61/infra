package main

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestRun(t *testing.T) {
	binPath, err := findShellCheckBin()
	if err != nil {
		t.Skip("no shellcheck bin found; skipping test")
	}

	outputDir, err := ioutil.TempDir("", "tricium-shellcheck-test")
	if err != nil {
		panic(err)
	}
	defer os.RemoveAll(outputDir)

	run("testdata", outputDir, binPath)

	resultsData, err := ioutil.ReadFile(filepath.Join(outputDir, "tricium/data/results.json"))
	if err != nil {
		panic(err)
	}

	var results map[string][]map[string]interface{}

	if err := json.Unmarshal(resultsData, &results); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	comments, ok := results["comments"]
	if !ok {
		t.Fatalf("results have no comments key")
	}

	if len(comments) != 1 {
		t.Fatalf("got %d comments want 1", len(comments))
	}

	comment := comments[0]
	assertMapKeyEqual(t, comment, "category", "ShellCheck/SC2034")
	assertMapKeyEqual(t, comment, "message",
		"warning: unused appears unused. Verify it or export it.")
	assertMapKeyEqual(t, comment, "url",
		"https://github.com/koalaman/shellcheck/wiki/SC2034")
	assertMapKeyEqual(t, comment, "path", "bad.sh")
	assertMapKeyEqual(t, comment, "startLine", float64(3))
	assertMapKeyEqual(t, comment, "endLine", float64(3))
}

func assertMapKeyEqual(t *testing.T, m map[string]interface{}, k string, want interface{}) {
	t.Helper()
	got, _ := m[k]
	if !reflect.DeepEqual(got, want) {
		t.Errorf("key %q got %v want %v", k, got, want)
	}
}
