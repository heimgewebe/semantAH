VENV=.venv
PY=$(VENV)/bin/python
PIP=$(PY) -m pip

.PHONY: venv index graph related all clean

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PY) -m pip install --upgrade pip
	@$(PIP) install pandas numpy pyarrow pyyaml sentence_transformers scikit-learn networkx rich

index: venv
	@$(PY) scripts/build_index.py

graph: venv
	@$(PY) scripts/build_graph.py

related: venv
	@$(PY) scripts/update_related.py

all: index graph related

clean:
	@rm -rf .gewebe
	@rm -rf notes_stub

