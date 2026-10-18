# TreeGov — Security and Privacy Audit (Phase 3.7.a)

**Purpose.** This document fulfills the requirements of Phase 3.7.a of the roadmap: a dedicated security and privacy audit of TreeGov before the v1.0.0 stable release. It defines the threat model, the data retention policy for logs, and the GUI warnings implemented to prevent accidental data leakage.

**Audience.** MRM auditors, security reviewers, and the project author.

## §0. Scope

TreeGov is a desktop application. It has no server, no remote authentication, no database, and no internet connection at runtime. The analyst loads a CSV, trains a model locally, and exports reports. 

This document covers the risks associated with **local data leakage** via the artefacts TreeGov generates: DEBUG logs and exported HTML reports.

## §1. Threat Model

### 1.1 Assets
- **The Dataset**: The CSV loaded by the analyst. Can contain sensitive PII or confidential financial data.
- **The Model**: The trained tree, including split rules, segment counts, and PD values.
- **The Artefacts**: The DEBUG logs (written to `logs/`) and the exported HTML reports.

### 1.2 Threat Vectors
- **Accidental Sharing of Logs**: A developer or analyst shares a `treegov_*.log` file for debugging, unaware that it contains real column names, file paths, and per-node PDs.
- **Accidental Sharing of Reports**: An analyst emails an HTML report to a colleague. The report contains the full gains table, classification matrix, and segment PDs.
- **Unintended GUI Exposure**: A screenshot of the TreeGov interface (e.g., the Tree Viewer or Reports panel) shared publicly reveals the structure of a proprietary model.

### 1.3 Mitigations
- **Log Retention Policy**: Explicit documentation that logs are ephemeral and should be cleaned.
- **GUI Warnings**: An explicit modal warning upon loading a dataset, reminding the analyst that the data and logs are confidential.
- **Documentation**: This document, serving as a reference for the institution's internal policies.

## §2. Log Retention and Cleanup

The `backend_v3.log_config` module writes to `logs/treegov.log` with `DEBUG` level. When training on real data, this log records:
- Column names from the CSV.
- PD per node and leaf distributions.
- File paths.
- Model fingerprints.

**Policy:** TreeGov does not auto-delete logs. The logs are owned by the analyst and subject to their institution's data retention policy. The analyst is responsible for deleting the `logs/` directory when the analysis is complete, or when moving the dataset off the machine.

## §3. HTML Reports

The `ReportsPanel` exports a self-contained HTML file. This file contains the gains table, classification matrix, and summary metrics. 

**Policy:** An exported HTML report is as sensitive as the dataset itself. It must be stored and transmitted according to the institution's data classification rules. TreeGov cannot enforce this once the file is saved to disk; it is the analyst's responsibility.

## §4. GUI Warnings

To mitigate the risk of accidental leakage, TreeGov implements a mandatory, non-blocking warning upon the first dataset load in a session. The warning reminds the analyst that:
- The dataset and generated logs are confidential.
- The logs must be cleaned up.
- The GUI does not encrypt files on disk.

This warning is shown once per session to avoid friction, but its presence is recorded in the log. 
