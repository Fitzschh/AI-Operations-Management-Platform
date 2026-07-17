"""Declarative workflow templates (Appendix C.3): named, versioned, parameterized step lists.

Templates are the value referenced by ``execute_workflow``'s ``template_name`` enum. Loading them
here (rather than accepting model-authored step lists) keeps HIGH-risk multi-step actions to a
pre-reviewed, human-authored set.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from touchorders_core.domain.common import DomainModel


class TemplateStep(DomainModel):
    tool: str
    args: dict[str, object] = {}
    args_from: str | None = None


class WorkflowTemplate(DomainModel):
    template: str
    version: int
    description: str = ""
    parameters: dict[str, str] = {}
    steps: list[TemplateStep]
    on_step_failure: str = "halt_and_compensate"


class TemplateLoadError(RuntimeError):
    pass


class TemplateLibrary:
    def __init__(self, templates: dict[str, WorkflowTemplate]) -> None:
        self._templates = templates

    @classmethod
    def from_directory(cls, directory: str | Path) -> "TemplateLibrary":
        path = Path(directory)
        templates: dict[str, WorkflowTemplate] = {}
        for yaml_file in sorted(path.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                template = WorkflowTemplate.model_validate(data)
            except Exception as exc:  # noqa: BLE001 - surface a bad template as a startup error
                raise TemplateLoadError(f"Invalid workflow template {yaml_file.name}: {exc}") from exc
            templates[template.template] = template
        return cls(templates)

    def names(self) -> list[str]:
        return sorted(self._templates)

    def get(self, name: str) -> WorkflowTemplate:
        try:
            return self._templates[name]
        except KeyError as exc:
            raise TemplateLoadError(f"Unknown workflow template {name!r}.") from exc
