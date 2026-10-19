.PHONY: generate test build verify browser serve
PYTHON ?= python
generate:
	$(PYTHON) scripts/generate.py
test:
	$(PYTHON) -m pytest -q --junitxml=docs/test-results.xml
build:
	$(PYTHON) scripts/build_site.py
verify: generate test build
browser:
	npm run test:browser
serve:
	$(PYTHON) -m http.server 8000 --directory dist
