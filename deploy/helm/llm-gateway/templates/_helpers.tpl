{{/* ==========================================================================
LLM Gateway - Helm Template Helpers
==========================================================================
This file contains helper templates used across all Helm templates.
========================================================================== */}}

{{/*
Expand the name of the chart.
Truncated to 63 characters (Kubernetes name limit).
*/}}
{{- define "llm-gateway.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this.
If release name contains chart name it will be used as a full name.
*/}}
{{- define "llm-gateway.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "llm-gateway.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
Follows Kubernetes recommended label conventions.
*/}}
{{- define "llm-gateway.labels" -}}
helm.sh/chart: {{ include "llm-gateway.chart" . }}
{{ include "llm-gateway.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: llm-document-enhancement
app.kubernetes.io/component: gateway
{{- end }}

{{/*
Selector labels used to identify pods belonging to this release.
These must be immutable after deployment.
*/}}
{{- define "llm-gateway.selectorLabels" -}}
app.kubernetes.io/name: {{ include "llm-gateway.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "llm-gateway.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "llm-gateway.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Redis URL helper - constructs Redis connection URL.
Uses subchart Redis if enabled, otherwise uses config.redisUrl.

Issue 19 Fix (Comp_Static_Analysis_Report_20251203.md):
When auth is enabled, password is NOT embedded in URL. Instead:
- Redis host/port returned without password
- Password provided separately via LLM_GATEWAY_REDIS_PASSWORD env var (secretKeyRef)
- Application constructs full URL at runtime (security best practice)
*/}}
{{- define "llm-gateway.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s-redis-master:6379" .Release.Name }}
{{- else }}
{{- .Values.config.redisUrl }}
{{- end }}
{{- end }}

{{/*
Create the image reference with repository and tag.
*/}}
{{- define "llm-gateway.image" -}}
{{- $tag := default .Chart.AppVersion .Values.image.tag }}
{{- printf "%s:%s" .Values.image.repository $tag }}
{{- end }}

{{/*
Service discovery URL helpers for inter-service communication.
*/}}
{{- define "llm-gateway.semanticSearchUrl" -}}
{{- if .Values.config.semanticSearchUrl }}
{{- .Values.config.semanticSearchUrl }}
{{- else }}
{{- printf "http://semantic-search.%s.svc.cluster.local:8081" .Release.Namespace }}
{{- end }}
{{- end }}

{{- define "llm-gateway.aiAgentsUrl" -}}
{{- if .Values.config.aiAgentsUrl }}
{{- .Values.config.aiAgentsUrl }}
{{- else }}
{{- printf "http://ai-agents.%s.svc.cluster.local:8082" .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Namespace helper - uses release namespace.
*/}}
{{- define "llm-gateway.namespace" -}}
{{- .Release.Namespace }}
{{- end }}
