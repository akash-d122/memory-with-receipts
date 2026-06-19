# Editor Extensions Runbook

## Editor Extensions

The Editor Extensions group is a collection of editors that extend GitLab features to developers across multiple phases of the DevSecOps cycle. Each contains its own quirks and deployment requirements. This runbook aims to place
all that information in once space. If anything is missing, contribute to this runbook to keep it up to date.

We currently support these editors:

- Visual Studio Code `~Editor Extensions::VS Code`
- Microsoft Visual Studio `~Editor Extensions::Visual Studio`
- JetBrains `~Editor Extensions::JetBrains`
- Eclipse `~Editor Extensions::Eclipse`
- Neovim `~Editor Extensions::NeoVim`

This group also uses the labels `~Group::editor extensions`, `~Category:Editor Extensions`, `~Editor Extensions::All`

## Install and setup

Each editor has its own steps for installation and setup:

- [Visual Studio Code](https://docs.gitlab.com/editor_extensions/visual_studio_code/setup/)
- [Microsoft Visual Studio](https://docs.gitlab.com/editor_extensions/visual_studio/setup/)
- [JetBrains](https://docs.gitlab.com/editor_extensions/jetbrains_ide/setup/)
- [Eclipse (Beta)](https://docs.gitlab.com/editor_extensions/eclipse/setup/)
- [NeoVim](https://docs.gitlab.com/editor_extensions/neovim/setup/)

Editor extensions are integrated with the
[GitLab Language Server](https://docs.gitlab.com/editor_extensions/language_server/). If that setup
is required for any part of your troubleshooting, please check out the
[GitLab project page](https://gitlab.com/gitlab-org/editor-extensions/gitlab-lsp).

## Troubleshooting

Each editor has its own troubleshooting documentation:

- [Visual Studio Code](https://docs.gitlab.com/editor_extensions/visual_studio_code/troubleshooting/)
- [Microsoft Visual Studio](https://docs.gitlab.com/editor_extensions/visual_studio/visual_studio_troubleshooting/)
- [JetBrains](https://docs.gitlab.com/editor_extensions/jetbrains_ide/jetbrains_troubleshooting/)
- [Eclipse](https://docs.gitlab.com/editor_extensions/eclipse/setup/)
- [NeoVim](https://docs.gitlab.com/editor_extensions/neovim/neovim_troubleshooting/)
- [Web IDE runbook](../web-ide/README.md)

## Request developer assistance and report bugs

Whether requesting developer assistance on a customer issue or submitting a bug report, the
Editor Extensions team works most efficiently when provided with all required information for support.

Use the [Dev Request for Help issue template](https://gitlab.com/gitlab-com/request-for-help/-/issues/new?description_template=SupportRequestTemplate-EditorExtensions)
to create a support issue for engineers on the Editor Extension team.

To help you fill out the template completely, see these pages for editor-specific instructions for
gathering the information we need:

### Required information for Support (RIFS)

- [Visual Studio Code RIFS](https://docs.gitlab.com/editor_extensions/visual_studio_code/troubleshooting/#required-information-for-support)
- [Microsoft Visual Studio RIFS](https://docs.gitlab.com/editor_extensions/visual_studio/visual_studio_troubleshooting/#required-information-for-support)
- [JetBrains RIFS](https://docs.gitlab.com/editor_extensions/jetbrains_ide/jetbrains_troubleshooting/#required-information-for-support)
- [Eclipse RIFS](https://docs.gitlab.com/editor_extensions/eclipse/troubleshooting/#required-information-for-support)
- NeoVim RIFS (Coming soon)

> Note: We aim to enhance this process by automating the collection of user environment details in the future.

## Contacting the Editor Extensions team

To streamline issue tracking and resolution, the preferred method for submitting an issue is to create a [Dev Request for Help](https://gitlab.com/gitlab-com/request-for-help/-/issues/new?description_template=SupportRequestTemplate-EditorExtensions) issue. Submitting an issue in this way will automatically notify the engineering manager who will triage and assign an appropriate developer for investigation.

For urgent matters, where all required information has already been collected, reach out via the appropriate Slack channel:

- Eclipse plugin: [`#f_eclipse_plugin`](https://gitlab.enterprise.slack.com/archives/C07MKHCFGHG)
- JetBrains plugin: [`#f_jetbrains_plugin`](https://gitlab.enterprise.slack.com/archives/C02UY9XKABH)
- Microsoft Visual Studio extension: [`#f_visual_studio_extension`](https://gitlab.enterprise.slack.com/archives/C0581SE363C)
- Neovim Plugin: [`#f_neovim_plugin`](https://gitlab.enterprise.slack.com/archives/C05BF7L6PEX)
- Visual Studio Code extension: [`#f_vscode_extension`](https://gitlab.enterprise.slack.com/archives/C013QJ9NEPL)
- General inquiries affecting multiple extensions: [`#g_editor_extensions`](https://gitlab.enterprise.slack.com/archives/C058YCHP17C)

## Documentation repository and knowledge base

This section is a centralized reference for troubleshooting Editor Extensions across multiple IDEs.
Given the varying levels of maturity for different editor integrations, documentation might not yet exist for all extensions.

If documentation is unavailable for a specific extension:

- See the [Contacting the Editor Extensions team](#contacting-the-editor-extensions-team) section for guidance.
- Contribute directly to this documentation or a specific editor's documentation pages.

### Add a new editor

If adding a new editor, update this runbook and create documentation to reflect the work done for other editors.
