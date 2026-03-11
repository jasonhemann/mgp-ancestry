.PHONY: gephi-open graphviz-render graphviz-open

PYTHON ?= python3
GEPHI_APP ?= /Applications/Gephi.app
PROJECT ?= gephi/projects/lineage_75750_explore.gephi
INPUT ?= ../out/lineage_75750.json
ID ?= 75750
FORMAT ?= all
OUTPUT_DIR ?= graphviz/generated/$(ID)

gephi-open:
	open -a "$(GEPHI_APP)" "$(PROJECT)"

graphviz-render:
	$(PYTHON) graphviz/renderer/render_graphviz.py \
		--input "$(INPUT)" \
		--output-dir "$(OUTPUT_DIR)" \
		--format "$(FORMAT)"

graphviz-open:
	open "$(OUTPUT_DIR)/lineage_$(ID).svg"
