.PHONY: check layout
layout:
	python3 skills/repository-organization/scripts/check_layout.py
	python3 skills/repository-organization/scripts/test_check_layout.py

check: layout
	python3 scripts/check_repository_structure.py
	python3 scripts/tests/test_repository_structure.py
	python3 scripts/sync_skills.py --check
	python3 scripts/sync_readme.py --check
	python3 scripts/tests/test_reader.py
	python3 scripts/check_contributions.py --self-test
