from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]

DIRECTORIES = [
    "raw/inbox",
    "raw/inbox/browser",
    "raw/inbox/clipboard",
    "raw/inbox/feeds",
    "raw/inbox/pdf-drop",
    "raw/articles",
    "raw/notes",
    "raw/pdfs",
    "compiled/source_summaries",
    "compiled/concepts",
    "compiled/topics",
    "outputs/reports",
    "outputs/answers",
    "templates",
    "metadata",
    "scripts",
]

TEMPLATE_FILES = {
    "templates/raw-note-template.md": dedent(
        """\
        ---
        title: ""
        source_type: ""
        origin: ""
        date_ingested: ""
        status: "draft"
        topics: []
        tags: []
        author: ""
        date_created: ""
        date_published: ""
        language: ""
        summary: ""
        source_id: ""
        canonical_url: ""
        related_sources: []
        confidence: ""
        license: ""
        ---

        # Overview

        Briefly describe what this source is and why it matters.

        # Source Content

        Capture the relevant source material, excerpts, structured notes, or a concise manual summary.

        # Key Points

        - Point 1
        - Point 2
        - Point 3

        # Notes

        Add interpretation, caveats, or follow-up questions here.

        # Lineage

        - Raw note path:
        - Original source:
        - Ingest method:
        - Related sources:
        """
    ),
    "templates/compiled-note-template.md": dedent(
        """\
        ---
        title: ""
        note_type: ""
        compiled_from: []
        date_compiled: ""
        topics: []
        tags: []
        confidence: ""
        generation_method: ""
        ---

        # Summary

        Summarize the combined understanding derived from the referenced raw notes.

        # Key Insights

        - Insight 1
        - Insight 2
        - Insight 3

        # Related Concepts

        - Concept or topic link

        # Source Notes

        - [[source-note-name]]

        # Lineage

        - Compiled from:
        - Compilation method:
        - Scope:
        """
    ),
    "templates/output-template.md": dedent(
        """\
        ---
        title: ""
        output_type: ""
        generated_from_query: ""
        generated_on: ""
        sources_used: []
        compiled_notes_used: []
        generation_method: ""
        ---

        # Prompt

        Record the user question, task, or prompt that produced this output.

        # Answer

        Write the generated answer here.

        # Sources Used

        - [[compiled-note-name]]
        - [[raw-note-name]]

        # Notes

        Add caveats, follow-up work, or limitations here.
        """
    ),
}

STARTER_FILES = {
    "raw/articles/aws-patch-manager-basics.md": dedent(
        """\
        ---
        title: "AWS Patch Manager Basics"
        source_type: "article-note"
        origin: "AWS Systems Manager Patch Manager documentation"
        date_ingested: "2026-04-03"
        status: "reviewed"
        topics:
          - "aws"
          - "patching"
          - "systems-manager"
        tags:
          - "aws"
          - "patch-manager"
          - "operations"
        author: "AWS"
        date_created: "2026-04-03"
        date_published: "2024-11-15"
        language: "en"
        summary: "Patch Manager helps automate operating system patching through patch baselines, patch groups, and maintenance windows."
        source_id: "src-aws-patch-manager-basics"
        canonical_url: "https://docs.aws.amazon.com/systems-manager/latest/userguide/patch-manager.html"
        related_sources:
          - "src-aws-inspector-overview"
        confidence: "medium"
        license: "See source site terms"
        ---

        # Overview

        AWS Systems Manager Patch Manager is used to automate patching for managed nodes. It provides a repeatable way to define approved patches and apply them during controlled maintenance windows.

        # Source Content

        Patch Manager centers on patch baselines, target selection, and scheduled execution. Teams usually combine it with maintenance windows and tagging strategies so that patching can be rolled out by environment or workload type.

        # Key Points

        - Patch baselines define which patches are approved or rejected.
        - Maintenance windows provide a controlled time to apply updates.
        - Patch groups and tags help scope patching to the right systems.

        # Notes

        This source is focused on operating system patching and operational control. It does not replace vulnerability assessment; it is better paired with a detection-oriented service.

        # Lineage

        - Raw note path: `raw/articles/aws-patch-manager-basics.md`
        - Original source: AWS Systems Manager Patch Manager documentation
        - Ingest method: manual markdown note
        - Related sources: `raw/articles/aws-inspector-overview.md`
        """
    ),
    "raw/articles/aws-inspector-overview.md": dedent(
        """\
        ---
        title: "AWS Inspector Overview"
        source_type: "article-note"
        origin: "Amazon Inspector documentation overview"
        date_ingested: "2026-04-03"
        status: "reviewed"
        topics:
          - "aws"
          - "vulnerability-management"
          - "security"
        tags:
          - "aws"
          - "inspector"
          - "security"
        author: "AWS"
        date_created: "2026-04-03"
        date_published: "2025-01-08"
        language: "en"
        summary: "Amazon Inspector continuously assesses AWS workloads for software vulnerabilities and unintended network exposure."
        source_id: "src-aws-inspector-overview"
        canonical_url: "https://docs.aws.amazon.com/inspector/latest/user/what-is-inspector.html"
        related_sources:
          - "src-aws-patch-manager-basics"
        confidence: "medium"
        license: "See source site terms"
        ---

        # Overview

        Amazon Inspector is a vulnerability management service that helps identify software vulnerabilities and exposure issues across supported AWS resources.

        # Source Content

        Inspector is oriented toward detection and visibility. It continuously evaluates supported resources and produces findings that can help teams prioritize remediation and validate where patching or configuration changes are needed.

        # Key Points

        - Inspector helps surface vulnerabilities and exposure findings.
        - Findings support prioritization of remediation work.
        - Inspector complements patching tools rather than replacing them.

        # Notes

        This source is useful as the detection side of the workflow. It should be linked with patching notes when building operational guidance for remediation programs.

        # Lineage

        - Raw note path: `raw/articles/aws-inspector-overview.md`
        - Original source: Amazon Inspector documentation overview
        - Ingest method: manual markdown note
        - Related sources: `raw/articles/aws-patch-manager-basics.md`
        """
    ),
    "compiled/topics/aws-patching-and-vulnerability-management-overview.md": dedent(
        """\
        ---
        title: "AWS Patching and Vulnerability Management Overview"
        note_type: "topic-overview"
        compiled_from:
          - "[[aws-patch-manager-basics]]"
          - "[[aws-inspector-overview]]"
        date_compiled: "2026-04-03"
        topics:
          - "aws"
          - "patching"
          - "vulnerability-management"
        tags:
          - "topic"
          - "aws"
          - "operations"
          - "security"
        confidence: "medium"
        generation_method: "manual compilation from raw notes"
        ---

        # Summary

        AWS patching and vulnerability management are related but distinct practices. Patch Manager is used to plan and execute operating system patching, while Inspector is used to identify vulnerabilities and exposure issues that inform remediation priorities.

        # Key Insights

        - `[[aws-patch-manager-basics]]` is primarily about controlled patch deployment.
        - `[[aws-inspector-overview]]` is primarily about continuous visibility into risk.
        - A practical workflow uses Inspector findings to inform what should be patched, then uses Patch Manager to execute approved updates on the right systems.

        # Related Concepts

        - Patch baselines
        - Maintenance windows
        - Vulnerability findings
        - Remediation prioritization

        # Source Notes

        - [[aws-patch-manager-basics]]
        - [[aws-inspector-overview]]

        # Lineage

        - Compiled from: [[aws-patch-manager-basics]] and [[aws-inspector-overview]]
        - Compilation method: manual synthesis of raw source notes
        - Scope: introductory overview for AWS patching and vulnerability management
        """
    ),
    "outputs/answers/sample-question-answer.md": dedent(
        """\
        ---
        title: "Sample Answer: How do AWS Patch Manager and Amazon Inspector work together?"
        output_type: "answer"
        generated_from_query: "How do AWS Patch Manager and Amazon Inspector work together in an MVP security operations workflow?"
        generated_on: "2026-04-03"
        sources_used:
          - "[[aws-patch-manager-basics]]"
          - "[[aws-inspector-overview]]"
        compiled_notes_used:
          - "[[aws-patching-and-vulnerability-management-overview]]"
        generation_method: "manual answer draft using compiled note and raw source notes"
        ---

        # Prompt

        How do AWS Patch Manager and Amazon Inspector work together in an MVP security operations workflow?

        # Answer

        Amazon Inspector helps identify vulnerable resources and provides findings that can be reviewed and prioritized. AWS Patch Manager then provides the operational mechanism to apply approved patches to the targeted systems during defined maintenance windows.

        In a simple MVP workflow, Inspector supplies visibility into what needs attention, while Patch Manager supplies the controlled remediation path. This keeps the detection and execution layers separate, which makes lineage clearer and avoids blending raw source material with generated outputs.

        # Sources Used

        - Compiled note: [[aws-patching-and-vulnerability-management-overview]]
        - Raw note: [[aws-patch-manager-basics]]
        - Raw note: [[aws-inspector-overview]]

        # Notes

        This output records the original prompt, the compiled note used for synthesis, and the raw notes used for verification. It is a generated artifact and must not overwrite raw source notes.
        """
    ),
    "metadata/source-manifest.json": dedent(
        """\
        {
          "manifest_version": "0.1.0",
          "last_updated": "2026-04-03",
          "description": "Minimal source manifest for tracking raw source notes and preserving lineage.",
          "sources": [
            {
              "source_id": "src-aws-patch-manager-basics",
              "title": "AWS Patch Manager Basics",
              "path": "raw/articles/aws-patch-manager-basics.md",
              "status": "reviewed"
            },
            {
              "source_id": "src-aws-inspector-overview",
              "title": "AWS Inspector Overview",
              "path": "raw/articles/aws-inspector-overview.md",
              "status": "reviewed"
            }
          ]
        }
        """
    ),
}


def ensure_directories() -> list[Path]:
    created = []
    for relative_path in DIRECTORIES:
        path = ROOT / relative_path
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        else:
            path.mkdir(parents=True, exist_ok=True)
    return created


def write_if_missing(relative_path: str, content: str) -> bool:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def create_files(file_map: dict[str, str]) -> list[Path]:
    created = []
    for relative_path, content in file_map.items():
        if write_if_missing(relative_path, content):
            created.append(ROOT / relative_path)
    return created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the MVP Knowledge Base directory structure and optional starter files."
    )
    parser.add_argument(
        "--with-templates",
        action="store_true",
        help="Create template files under templates/ if they are missing.",
    )
    parser.add_argument(
        "--with-starters",
        action="store_true",
        help="Create example starter notes and metadata files if they are missing.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    created_directories = ensure_directories()
    created_templates = create_files(TEMPLATE_FILES) if args.with_templates else []
    created_starters = create_files(STARTER_FILES) if args.with_starters else []

    print(f"Project root: {ROOT}")
    print(f"Directories ensured: {len(DIRECTORIES)}")
    print(f"Directories newly created: {len(created_directories)}")
    print(f"Templates newly created: {len(created_templates)}")
    print(f"Starter files newly created: {len(created_starters)}")

    if created_templates:
        print("\nCreated templates:")
        for path in created_templates:
            print(f"- {path.relative_to(ROOT)}")

    if created_starters:
        print("\nCreated starter files:")
        for path in created_starters:
            print(f"- {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
