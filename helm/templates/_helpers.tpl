{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "moirai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "moirai.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "moirai.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "moirai.labels" -}}
helm.sh/chart: {{ include "moirai.chart" . }}
{{ include "moirai.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "moirai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "moirai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "moirai.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "moirai.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{/*
API name
*/}}
{{- define "moirai.api.name" -}}
{{- printf "%s-%s" (include "moirai.name" .) "api" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
UI name
*/}}
{{- define "moirai.ui.name" -}}
{{- printf "%s-%s" (include "moirai.name" .) "ui" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Nginx name
*/}}
{{- define "moirai.nginx.name" -}}
{{- printf "%s-%s" (include "moirai.name" .) "nginx" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
AISA env vars mapped from the AISA-managed consumer Secret.
Uses secretKeyRef (not envFrom) so the Secret's OPENAI_API_KEY cannot collide
with the direct OPENAI_API_KEY env var; optional so pods start pre-reconcile.
With aisa.keyFile (default) the key is read from the mounted Secret instead
(AISA_API_KEY_FILE): kubelet refreshes the file in place, so a key rotation
needs no restart and no Reloader. Pair with moirai.aisaVolumeMounts/Volumes.
*/}}
{{- define "moirai.aisaEnv" -}}
{{- if .Values.aisa.enabled }}
- name: AISA_BASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.aisa.secretName | quote }}
      key: OPENAI_BASE_URL
      optional: true
{{- if .Values.aisa.keyFile }}
- name: AISA_API_KEY_FILE
  value: {{ printf "%s/OPENAI_API_KEY" .Values.aisa.keyMountPath | quote }}
{{- else }}
- name: AISA_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.aisa.secretName | quote }}
      key: OPENAI_API_KEY
      optional: true
{{- end }}
{{- if .Values.aisa.defaultModel }}
- name: AISA_MODEL
  value: {{ .Values.aisa.defaultModel | quote }}
{{- else }}
- name: AISA_MODEL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.aisa.secretName | quote }}
      key: OPENAI_MODEL
      optional: true
{{- end }}
{{- end }}
{{- end -}}

{{/*
Mount of the AISA consumer Secret for AISA_API_KEY_FILE. The whole Secret is
mounted (no subPath, which kubelet never refreshes); optional so pods start
before AISA has reconciled it, and kubelet fills it in once it exists.
*/}}
{{- define "moirai.aisaVolumeMounts" -}}
{{- if and .Values.aisa.enabled .Values.aisa.keyFile -}}
- name: aisa-key
  mountPath: {{ .Values.aisa.keyMountPath | quote }}
  readOnly: true
{{- end }}
{{- end -}}

{{- define "moirai.aisaVolumes" -}}
{{- if and .Values.aisa.enabled .Values.aisa.keyFile -}}
- name: aisa-key
  secret:
    secretName: {{ .Values.aisa.secretName | quote }}
    optional: true
{{- end }}
{{- end -}}

{{/*
Deployment annotations for Stakater Reloader (restart when the AISA Secret
changes). Requires Reloader in the cluster; without it this does nothing.
With aisa.keyFile the key rotates without it; Reloader then only matters for
OPENAI_BASE_URL / OPENAI_MODEL changes, which are read as env at start.
*/}}
{{- define "moirai.aisaReloaderAnnotations" -}}
{{- if and .Values.aisa.enabled .Values.aisa.reloader }}
secret.reloader.stakater.com/reload: {{ .Values.aisa.secretName | quote }}
{{- end }}
{{- end -}}

{{/*
Model catalog (llm.catalog + llm.purposes) rendered as JSON into a ConfigMap
and read through LLM_CATALOG_FILE. Rendered only when llm.catalog has entries;
without it the services keep the legacy env configuration. The ConfigMap is
mounted as a directory (no subPath), so kubelet refreshes it in place and the
services pick up changes without a restart.
*/}}
{{- define "moirai.llmCatalogEnabled" -}}
{{- if .Values.llm.catalog }}true{{ end }}
{{- end -}}

{{- define "moirai.llmEnv" -}}
{{- include "moirai.aisaEnv" . }}
{{- if include "moirai.llmCatalogEnabled" . }}
- name: LLM_CATALOG_FILE
  value: {{ printf "%s/catalog.json" .Values.llm.catalogMountPath | quote }}
{{- end }}
{{- end -}}

{{- define "moirai.llmVolumeMounts" -}}
{{- include "moirai.aisaVolumeMounts" . }}
{{- if include "moirai.llmCatalogEnabled" . }}
- name: llm-catalog
  mountPath: {{ .Values.llm.catalogMountPath | quote }}
  readOnly: true
{{- end }}
{{- end -}}

{{- define "moirai.llmVolumes" -}}
{{- include "moirai.aisaVolumes" . }}
{{- if include "moirai.llmCatalogEnabled" . }}
- name: llm-catalog
  configMap:
    name: {{ include "moirai.fullname" . }}-llm-catalog
{{- end }}
{{- end -}}
