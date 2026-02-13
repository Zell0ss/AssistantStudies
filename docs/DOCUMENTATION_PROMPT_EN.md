# Documentation Generation Prompt for Claude Code

> **Instructions for Claude Code**: Read this complete document before generating project documentation.

---

## Objective

Generate minimalist but effective documentation for Python projects. The audience is both "future me" (the developer returning after months) and potential external contributors.

---

## Required Structure

Generate these files (UPPERCASE names):

```
README.md              # Elevator pitch + quick start
BRIEFING.md            # Context for Claude ↔ Claude transfer (MANDATORY)
ARCHITECTURE.md        # Design decisions + data flow diagram
QUICKSTART.md          # 5-minute tutorial
CHANGELOG.md           # (only if doesn't exist)
docs/                  # (create if needed)
  HOW-TO-*.md          # Specific use cases
.env.example           # Configuration template
```
*Important*: the docs folder should be under the root of the project. if there is another doc folder, ignore it and create the one under the project folder.

**Priority order**:
1. **Mandatory**: README, BRIEFING, ARCHITECTURE, QUICKSTART
2. **Recommended**: .env.example, HOW-TO-*.md (based on complexity)
3. **Optional**: CHANGELOG (only if doesn't exist)

---

## 1. README.md

**Purpose**: Answer in 30 seconds what the project is about.

**Structure**:

```markdown
# [ProjectName]

[One-line description: what it does and what for]

## Quick Start

\```bash
# Installation (3-4 commands)
pip install -r requirements.txt
cp .env.example .env

# Basic usage (1-2 commands)
python main.py [main-command]
\```

## What it does

- [Main feature 1]
- [Main feature 2]
- [Main feature 3]

## Documentation

- 📖 [Architecture](ARCHITECTURE.md) - How it works
- 🚀 [Quick Start](QUICKSTART.md) - Complete tutorial
- 🛠️ [How-to guides](docs/) - Use cases

## Requirements

- Python 3.11+
- [Critical dependencies]
```

**Rules**:
- Description maximum 1 line
- Quick Start maximum 6 commands
- Features in bullets, not paragraphs
- NO long explanations (those go in ARCHITECTURE)

---

## 2. ARCHITECTURE.md

**Purpose**: Explain design decisions and how it works internally.

**Required structure**:

```markdown
# [Project] - Architecture

## The Problem

[1-2 paragraphs: what problem does the project solve]

## The Solution

[Mermaid diagram of main data flow]

\```mermaid
graph LR
    A[Input Source] --> B[Processing]
    B --> C{Decision}
    C -->|Path A| D[Output A]
    C -->|Path B| E[Output B]
\```

## Key Decisions

### Why [Technology/Pattern X]?

**Context**: [Why it was needed]

**Options considered**:
1. Option A - [Pros/Cons]
2. Option B - [Pros/Cons]
3. Option C - [Pros/Cons]

**Decision**: [Chosen option]

**Reasons**:
- Reason 1
- Reason 2
- Reason 3

**Trade-off accepted**: [What was sacrificed with this decision]

[Repeat for each important decision]

## Data Flow

[Step-by-step description of main flow]

1. **[Step 1]**: [What happens]
   - Input: [Format]
   - Output: [Format]
2. **[Step 2]**: [What happens]
   - [Relevant details]
3. [...]

## Main Components

### [Component 1]

**Responsibility**: [What it does]

**Inputs**: [What it receives]

**Outputs**: [What it produces]

**Dependencies**: [What it needs]

[Repeat for key components]
```

**Specific instructions**:

1. **Mermaid Diagram**:
   - Maximum 7 nodes
   - Use `graph LR` (left-right) or `graph TD` (top-down)
   - Clear names in nodes (no abbreviations)
   - Labels on arrows for decisions

2. **Key Decisions**:
   - Document ONLY non-obvious decisions
   - Include discarded alternatives
   - Explain accepted trade-offs

3. **Questions it should answer**:
   - Why this architecture?
   - Why these technologies?
   - What happens to data step by step?
   - Where are potential bottlenecks?

---

## 3. QUICKSTART.md

**Purpose**: Step-by-step tutorial to use the project for the first time.

**Structure**:

```markdown
# Quick Start: [Project]

In this guide you'll use [project] to [concrete goal].

**Estimated time**: 5 minutes

## Prerequisites

- Python 3.11+
- [Other critical dependencies]

## Step 1: Installation

\```bash
git clone [url if applicable]
cd [project]
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
\```

## Step 2: Configuration

\```bash
cp .env.example .env
# Edit .env and add:
#   REQUIRED_VARIABLE=your-value-here
\```

Critical variables:
- `VARIABLE_1`: [Where to get it]
- `VARIABLE_2`: [What it's for]

## Step 3: First use

\```bash
[main-command] [args]
\```

**Expected output**:
\```
✓ [Expected success message]
\```

## Step 4: Verify result

\```bash
[verification command]
# or
cat [output-file]
\```

## Next steps

- [Link to relevant HOW-TO]
- [Link to ARCHITECTURE to understand more]
```

**Rules**:
- Maximum 5 steps
- Each step must have expected output
- Include commands for Linux/Mac AND Windows if they differ
- Links at the end to dive deeper

---

## 4. docs/HOW-TO-*.md

**When to create**: If the use case:
- Is recurrent
- Has >5 steps
- Requires decisions (not linear)

**Common examples**:
- `HOW-TO-DEPLOY.md` - Configure as service/cron
- `HOW-TO-ADD-[FEATURE].md` - Extend functionality
- `HOW-TO-TROUBLESHOOT.md` - Common problems

**Structure**:

```markdown
# How to [Specific Action]

## Goal

By the end of this guide you will have [concrete result].

## Context

[1-2 sentences about when you need this]

## Steps

### 1. [First step]

\```bash
[commands]
\```

**Why**: [Brief explanation if not obvious]

### 2. [Second step]

\```python
# Example code if applicable
\```

**Alternatives**: [If there are other ways to do it]

### 3. Verify

\```bash
[verification command]
\```

**Expected output**:
\```
✓ [OK output]
\```

## Troubleshooting

### Problem: [Common error 1]

**Cause**: [Why it happens]

**Solution**:
\```bash
[fix command]
\```

### Problem: [Common error 2]

**Solution**: [How to resolve it]
```

---

## 5. CHANGELOG.md

**Only if doesn't exist**. If it exists, don't touch.

**Structure**:

```markdown
# Changelog

## [Unreleased]

### Added
- [New feature pending release]

### Changed
- [Change in existing feature]

### Fixed
- [Bug fixed]

## [1.0.0] - YYYY-MM-DD

First functional version.
```

---

## 6. .env.example

**Configuration template** with all variables without secret values.

**Structure**:

```bash
# === REQUIRED ===

# [Variable description]
# Get it at: [URL or process]
REQUIRED_VARIABLE=

# [Another variable]
OTHER_VARIABLE=


# === OPTIONAL ===

# [Description]
# Default: [default value]
OPTIONAL_VARIABLE=

# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=project_name
```

**Rules**:
- Required variables first
- Comments explain where to get values
- Include defaults when applicable
- DO NOT include real/secret values

---

## 7. BRIEFING.md

**Purpose**: Context document optimized for knowledge transfer between Claude Code and Claude Web, and as project executive summary.

**When to create**: 
- Projects with >500 lines of code
- If you'll use Claude Web to discuss architecture
- If you need quick onboarding for yourself after months

**Audience**: Claude AI (Code and Web) and the developer

**Structure**:

```markdown
# [Project] - Briefing for Claude

> **Purpose**: Knowledge transfer between Claude Code and Claude Web.
> **Audience**: Claude AI and developer

---

## What is this project

[2-3 lines: what it does, what for, main use case]

---

## How it works (data flow)

\```
1. INGESTION: [Source] → [Raw format]
2. PROCESSING: [Main process] → [Transformation]
3. STORAGE: [Where it's saved]
4. OUTPUT: [Final result]
\```

Detailed explanation:
[2-3 paragraphs explaining end-to-end flow]

---

## Tech stack

- **Language**: Python 3.X
- **Main Frameworks/Libs**: 
  - [Lib 1]: [What for]
  - [Lib 2]: [What for]
- **Database**: [Type] - [Reason for choice in 1 line]
- **External APIs**: 
  - [API 1]: [What for]
  - [API 2]: [What for]
- **Infrastructure**: [Local/Cloud/Hybrid]

---

## Main CLI commands

| Command | What it does | Usage example |
|---------|--------------|---------------|
| `cmd1 <args>` | [Brief description] | `cmd1 --flag value` |
| `cmd2` | [Brief description] | `cmd2` |
| `cmd3 [opts]` | [Brief description] | `cmd3 --output file.txt` |

---

## Project structure

\```
project/
├── src/
│   ├── [module1]/     # [Main responsibility]
│   ├── [module2]/     # [Main responsibility]
│   └── main.py        # CLI entry point
├── tests/             # Tests with pytest
├── data/              # [What it contains]
└── outputs/           # [What's generated here]
\```

**Key modules**:
- **[module1]**: [What it does, why it exists]
- **[module2]**: [What it does, interaction with others]

---

## Critical design decisions

### [Decision 1: Concise title]

**Why**: [Main reason in 1-2 lines]

**Discarded alternatives**: [Option A], [Option B]

**Accepted trade-off**: [What was sacrificed with this decision]

---

### [Decision 2: Concise title]

**Why**: [Reason]

**Impact**: [How it affects the rest of the system]

---

[Repeat for 3-5 most important decisions]

---

## Data and models

### Main data model

**Main entity**: [EntityName]

Key fields:
- `field1`: [Type] - [Purpose, validations]
- `field2`: [Type] - [Purpose, validations]
- `field3`: [Type] - [Purpose, validations]

**Relationships**: [If there are relationships between entities, describe them]

---

### Data transformation flow

\```
[Input Format] 
  → [Process 1: validation/cleaning] 
  → [Intermediate Format] 
  → [Process 2: transformation] 
  → [Output Format]
\```

**Formats**:
- Input: [Input format description]
- Output: [Output format description]

---

## Configuration

### Critical environment variables

**Required**:
- `VAR_REQUIRED_1`: [Where to get it, expected format]
- `VAR_REQUIRED_2`: [Where to get it, what it's used for]

**Optional**:
- `VAR_OPTIONAL_1`: [Default: X, when to change]
- `VAR_OPTIONAL_2`: [Default: Y, purpose]

### Configuration files

[If applicable: location, format (YAML/JSON/INI), what they configure]

---

## Current state

**Version**: [X.Y.Z]

**Last update**: [Date - Month YYYY]

### Features

✅ **Implemented**:
- [Feature 1]
- [Feature 2]
- [Feature 3]

🚧 **In development**:
- [Feature in progress, if applicable]

📋 **Known TODOs**:
- [Pending improvement 1]
- [Pending improvement 2]

---

## Typical use cases

### Case 1: [Descriptive name]

**Goal**: [What user wants to achieve]

**Flow**:
1. [Step 1 with command]
2. [Step 2 with command]
3. [Expected result]

**Example**:
\```bash
example command arg1 arg2
\```

---

### Case 2: [Descriptive name]

**Goal**: [What to achieve]

**Flow**:
1. [Step]
2. [Step]
3. [Result]

---

[Include 2-3 most common use cases]

---

## Limitations and caveats

### Known limitations

- **Limitation 1**: [What it can't do and why]
- **Limitation 2**: [Technical or design restriction]

### Non-intuitive behaviors

- **Caveat 1**: [Behavior that might surprise]
- **Caveat 2**: [Edge case to keep in mind]

---

## Development context

**Original motivation**: [Why this project was created]

**Evolution**: [If it changed from initial idea]

**Current usage**: 
- Frequency: [Daily/Weekly/Monthly/Ad-hoc]
- Context: [When and how it's used]

---

## Key code patterns

### Most common usage pattern

\```python
# [Explanation: when to use this pattern]
# Concrete example of typical usage
example_code()
\```

---

### Extension pattern

\```python
# How to add [common feature, e.g.: new data source]
# Template followed in the project

class NewFeature(BaseClass):
    def required_method(self):
        # Implementation
        pass
\```

---

## Notes for Claude Web

**Context for architecture discussions**:
- [Useful information to understand decisions]
- [Project restrictions or requirements]

**Pending decisions**:
- [Architectural decision requiring input]

**Improvement areas**:
- [Where the project could be optimized]

---

## Notes for Claude Code

**Project conventions**:
- [Specific code style]
- [Patterns consistently followed]

**Areas requiring attention**:
- [Modules with technical debt]
- [Code needing refactoring]

**When contributing**:
- [Pattern to follow for new features]
- [Tests required before merge]

---

*Last updated: [Date]*  
*Generated from: [commit hash or "current code"]*
\```

**Specific instructions for generating BRIEFING**:

1. **Target length**: 2-3 pages (no more)
2. **Tone**: Technical but direct, optimized for quick reading
3. **Prioritize**: Decisions over implementation, "why" over "how"
4. **Include**: Only what's needed for another Claude to understand the project without seeing code

**BRIEFING use cases**:
- Claude Web reads this before discussing architecture
- Claude Code reads this to understand context before contributing
- Developer reads this as executive summary when returning to project
- Quick onboarding (5-10 minutes reading)

---

## Generation Checklist

Before delivering, verify:

### README.md
- [ ] Clear 1-line description
- [ ] Quick Start works (mentally tested)
- [ ] Features in bullets
- [ ] Links to other docs

### ARCHITECTURE.md
- [ ] Mermaid diagram present and useful
- [ ] At least 2 "Key Decisions" documented
- [ ] Step-by-step data flow
- [ ] Answers "why this way?"

### QUICKSTART.md
- [ ] Maximum 5 steps
- [ ] Expected output in each step
- [ ] Estimated time included
- [ ] Links to next steps

### BRIEFING.md
- [ ] Complete tech stack
- [ ] Critical decisions documented (2-4)
- [ ] Typical use cases (2-3)
- [ ] Main CLI commands listed
- [ ] Specific notes for Claude Web and Claude Code
- [ ] Length: 2-3 pages maximum

### General
- [ ] File names in UPPERCASE
- [ ] Code in markdown blocks with syntax
- [ ] No TODOs or placeholders
- [ ] Terminology consistency

---

## Execution Instructions

1. **Analyze the project**:
   - Read current README (if exists)
   - Identify main technologies
   - Identify main data flow
   - Detect non-obvious architectural decisions

2. **Generate documents in order**:
   1. README.md
   2. BRIEFING.md (new - critical for Claude ↔ Claude exchange)
   3. ARCHITECTURE.md (most detailed)
   4. QUICKSTART.md
   5. docs/HOW-TO-*.md (based on detected use cases)
   6. .env.example
   7. CHANGELOG.md (only if doesn't exist)

3. **Prioritize**:
   - **Mandatory**: README + BRIEFING + ARCHITECTURE + QUICKSTART
   - **Optional based on complexity**: HOW-TOs, REFERENCE
   - **Only if doesn't exist**: CHANGELOG

4. **Style**:
   - Tone: Direct, telegraphic
   - Audience: "Future me" (human) and Claude (AI)
   - Assume: Python and development knowledge
   - DO NOT assume: Remembering project details

---

## Examples of Well-Documented Decisions

### ✅ Good example

```markdown
### Why MariaDB instead of SQLite?

**Context**: Need to cache posts from multiple sources without re-processing

**Options considered**:
1. SQLite - Simple, zero config
2. MariaDB - Better concurrency
3. Redis - Fast cache

**Decision**: MariaDB

**Reasons**:
- Future plan: web dashboard will need concurrent reads
- Redis doesn't persist data after restart
- Already use MariaDB in other projects → zero mental setup

**Trade-off**: Requires running server (vs SQLite file-based)
```

### ❌ Bad example

```markdown
### Database

Using MariaDB because it's better.
```

---

## Final Notes

- **Minimalism**: Only document what's necessary
- **Clarity**: Prefer clarity over extreme brevity
- **Maintainability**: Easy-to-update docs
- **Utility**: Each doc should answer specific questions

If in doubt about whether to document something: **Document decisions, not implementation.**