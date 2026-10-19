# Vendored PyRIT attack data

The files in this directory are copied, unmodified, from Microsoft PyRIT
(Python Risk Identification Tool for generative AI), version 1.1.0, which is
released under the MIT License (see LICENSE in this directory).

- `jailbreak/*.yaml` — adversarial prompt templates from
  `pyrit/datasets/jailbreak/templates/`
- `seeds/psfuzz_steal_system.prompt` — system-prompt-extraction seed from
  `pyrit/datasets/seed_datasets/local/`

Source: https://github.com/Azure/PyRIT

Why vendored: the auditor prefers the installed `pyrit` package as its attack
source when it is importable (see `app/auditor/attack_source.py`). These copies
let the project and its CI run without installing PyRIT's full runtime. They are
the *attack phrasings*; the benign banking test objectives this project adds
live in `attacks/objectives.yaml`.
