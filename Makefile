# Smart Exam Proctoring — Makefile
.PHONY: help install lint test run docker-build docker-run clean

help:
	@echo "Smart Exam Proctoring — Make targets"
	@echo ""
	@echo "  install      Install Python dependencies"
	@echo "  lint         Run ruff + mypy checks"
	@echo "  test         Run syntax/type checks"
	@echo "  run          Start dashboard locally (port 5001)"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run dashboard in Docker"
	@echo "  clean        Remove cache and temp files"

install:
	pip install -r requirements.txt

lint:
	pip install ruff mypy >/dev/null 2>&1
	ruff check . --ignore=E501,W293
	mypy --ignore-missing-imports dashboard.py robot_controller.py object_detector.py || true

test:
	python -m py_compile dashboard.py robot_controller.py object_detector.py \
	  face_detector.py eye_gaze.py person_detector.py \
	  boundary_zones.py scoring_system.py camera_capture.py

run:
	python dashboard.py

docker-build:
	docker build -t smart-exam:latest .

docker-run:
	docker run --rm -p 5001:5001 \
	  --device=/dev/video0:/dev/video0 \
	  -v $(PWD)/evidence:/app/evidence \
	  smart-exam:latest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache

# Git LFS helpers
lfs-track:
	git lfs install
	git lfs track "yolov8n.pt"
	git add .gitattributes yolov8n.pt
	git commit -m "Track yolov8n.pt with Git LFS"

lfs-pull:
	git lfs pull