# _helpers.tpl
{{- define "common.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.Version }}
app.kubernetes.io/part-of: {{ .Values.app.name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Generates a comma delimited list of nodes in the cluster
*/}}
{{- define "couchdb.seedlist" -}}
{{- $nodeCount :=  min 5 .Values.couchdb.replicas | int }}
  {{- range $index0 := until $nodeCount -}}
    {{- $index1 := $index0 | add1 -}}
    {{ $.Values.couchdb.erlangFlags.name }}@{{ template "fullname" $ }}-{{ $index0 }}.{{ template "fullname" $ }}.{{ $.Release.Namespace }}.svc.{{ $.Values.dns.clusterDomainSuffix }}{{ if ne $index1 $nodeCount }},{{ end }}
  {{- end -}}
{{- end -}}
