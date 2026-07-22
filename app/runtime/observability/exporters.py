import json
import csv
from io import StringIO
from typing import List
from runtime.observability.domain.ports import ExporterPort
from runtime.observability.domain.models import MetricFamily, Span, Alert

class ConsoleExporter(ExporterPort):
    """Prints metrics, spans, and alert logs to console stdout."""
    def export_metrics(self, families: List[MetricFamily]) -> None:
        for f in families:
            print(f"[ConsoleExporter] MetricFamily: {f.name} ({f.metric_type}) - {len(f.metrics)} series")

    def export_spans(self, spans: List[Span]) -> None:
        for s in spans:
            print(f"[ConsoleExporter] Span: {s.name} ({s.span_id}) - trace={s.trace_id}")

    def export_alerts(self, alerts: List[Alert]) -> None:
        for a in alerts:
            print(f"[ConsoleExporter] Alert: {a.rule_name} - {a.severity}: {a.message}")


class JSONExporter(ExporterPort):
    """Serializes gathered telemetry to JSON formatted strings."""
    def export_metrics(self, families: List[MetricFamily]) -> str:
        return json.dumps([f.to_dict() for f in families])

    def export_spans(self, spans: List[Span]) -> str:
        return json.dumps([s.to_dict() for s in spans])

    def export_alerts(self, alerts: List[Alert]) -> str:
        return json.dumps([a.to_dict() for a in alerts])


class CSVExporter(ExporterPort):
    """Outputs data rows as CSV formatted strings."""
    def export_metrics(self, families: List[MetricFamily]) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["FamilyName", "MetricType", "MetricKey", "Timestamp", "Value"])
        
        for f in families:
            for key, metric in f.metrics.items():
                for pt in metric.points:
                    writer.writerow([f.name, f.metric_type, key, pt.timestamp, pt.value])
        return output.getvalue()

    def export_spans(self, spans: List[Span]) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["SpanID", "TraceID", "Name", "StartTime", "EndTime", "ParentSpanID"])
        
        for s in spans:
            writer.writerow([s.span_id, s.trace_id, s.name, s.start_time, s.end_time, s.parent_span_id])
        return output.getvalue()

    def export_alerts(self, alerts: List[Alert]) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["RuleName", "Severity", "Message", "Timestamp"])
        
        for a in alerts:
            writer.writerow([a.rule_name, a.severity, a.message, a.timestamp])
        return output.getvalue()


# Extension Ports/Adapters definitions (no external library integration code)

class OpenTelemetryExporter(ExporterPort):
    """Extension adapter mapping Mollis spans to standard OpenTelemetry Collector protocols."""
    def export_metrics(self, families: List[MetricFamily]) -> None:
        raise NotImplementedError("OpenTelemetry metrics push requires 'opentelemetry-sdk' integration package.")

    def export_spans(self, spans: List[Span]) -> None:
        raise NotImplementedError("OpenTelemetry distributed spans push requires 'opentelemetry-sdk' integration package.")

    def export_alerts(self, alerts: List[Alert]) -> None:
        raise NotImplementedError("OpenTelemetry alerts push requires OTLP logging mapping protocols.")


class PrometheusExporter(ExporterPort):
    """Extension adapter rendering metrics in standard Prometheus line formats."""
    def export_metrics(self, families: List[MetricFamily]) -> None:
        raise NotImplementedError("Prometheus export mapping requires 'prometheus_client' package integration.")

    def export_spans(self, spans: List[Span]) -> None:
        pass

    def export_alerts(self, alerts: List[Alert]) -> None:
        pass


class GrafanaExporter(ExporterPort):
    """Extension adapter exporting directly to Grafana Cloud Loki or Loki Push API endpoints."""
    def export_metrics(self, families: List[MetricFamily]) -> None:
        pass

    def export_spans(self, spans: List[Span]) -> None:
        pass

    def export_alerts(self, alerts: List[Alert]) -> None:
        pass
