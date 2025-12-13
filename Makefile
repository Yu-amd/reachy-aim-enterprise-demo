.PHONY: venv install sim run

venv:
	python -m venv .venv

install:
	. .venv/bin/activate && pip install -U pip && pip install -e .

sim:
	. .venv/bin/activate && pip install "reachy-mini[mujoco]" && reachy-mini-daemon --sim

run:
	. .venv/bin/activate && python -m reachy_demo.main run
