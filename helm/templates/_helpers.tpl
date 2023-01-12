{{- define "serverName" }}
{{- if eq .Values.deployType "PROD"}} "LCA Project"{{- else}} "LCA Dev"{{- end}}
{{- end}}