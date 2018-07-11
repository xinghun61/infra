package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"sort"
	"strings"
)

var fieldTypeMap = map[string]string{"string": "string", "number": "double", "integer": "int64"}

func getRef(schema map[string]interface{}, ref string) map[string]interface{} {
	parts := strings.Split(ref, "/")
	definitions := schema["definitions"].(map[string]interface{})
	spec := definitions[parts[2]].(map[string]interface{})
	return spec
}

func getType(schema map[string]interface{}, name string, spec map[string]interface{}) (string, bool) {
	if ref, ok := spec["$ref"].(string); ok {
		return getType(schema, name, getRef(schema, ref))
	}
	if _, ok := spec["enum"]; ok {
		return "string", false
	}
	fieldType := spec["type"].(string)
	if fieldType == "array" {
		items := spec["items"].(map[string]interface{})
		fieldType, _ := getType(schema, name, items)
		return fieldType, true
	}
	protoType := fieldTypeMap[fieldType]
	return protoType, false
}

func schemaToProto(schema map[string]interface{}) string {
	fields := schema["properties"].(map[string]interface{})
	// Sort fields by name, so the proto output is deterministic.
	fieldNames := make([]string, 0, len(fields))
	for name := range fields {
		fieldNames = append(fieldNames, name)
	}
	sort.Strings(fieldNames)
	proto := "syntax = \"proto2\";\n"
	proto += "package metrics;\n"
	proto += "message MetricsSchema {\n"
	for fieldNum, name := range fieldNames {
		spec := fields[name].(map[string]interface{})
		fieldType, isRepeated := getType(schema, name, spec)
		if isRepeated {
			fieldType = "repeated " + fieldType
		} else {
			fieldType = "optional " + fieldType
		}
		proto += fmt.Sprintf("  %s %s = %d;\n", fieldType, name, fieldNum+1)
	}
	proto += "}\n"
	return proto
}

func main() {
	if len(os.Args) != 3 {
		err := "Usage: schema2proto [path-to-json-schema] [path-to-proto]"
		panic(err)
	}

	contents, err := ioutil.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}

	var schema map[string]interface{}

	if err := json.Unmarshal(contents, &schema); err != nil {
		panic(err)
	}

	proto := schemaToProto(schema)
	if err := ioutil.WriteFile(os.Args[2], []byte(proto), 0755); err != nil {
		panic(err)
	}
}
