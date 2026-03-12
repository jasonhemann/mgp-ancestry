.PHONY: gephi-open graphviz-render graphviz-open

PYTHON ?= python3
GEPHI_APP ?= /Applications/Gephi.app
INPUT ?=
ID ?=
FORMAT ?= all
OUTPUT_DIR ?= graphviz/generated/$(ID)

gephi-open:
	@if [ -n "$(INPUT)" ]; then \
		open -a "$(GEPHI_APP)" "$(INPUT)"; \
	else \
		open -a "$(GEPHI_APP)"; \
	fi

graphviz-render:
	@if [ -z "$(INPUT)" ] || [ -z "$(ID)" ]; then \
		echo "Usage: make graphviz-render INPUT=../out/lineage_<id>.json ID=<id> [FORMAT=svg|png|dot|all]"; \
		exit 1; \
	fi
	$(PYTHON) graphviz/renderer/render_graphviz.py \
		--input "$(INPUT)" \
		--output-dir "$(OUTPUT_DIR)" \
		--format "$(FORMAT)"

graphviz-open:
	@if [ -z "$(ID)" ]; then \
		echo "Usage: make graphviz-open ID=<id>"; \
		exit 1; \
	fi
	open "$(OUTPUT_DIR)/lineage_$(ID).svg"
