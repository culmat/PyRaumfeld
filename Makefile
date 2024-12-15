.DEFAULT_GOAL := help

run:
	python3 RaumfeldControl.py

build:
	docker build -t pyraumfeld .

run-docker:
	docker run --rm -it --network host pyraumfeld

clean:
	find . -name '__pycache__' -type d -exec rm -rf {} +
	docker ps -a | grep pyraumfeld | awk '{print $1}' | xargs -r docker rm
	docker images | grep pyraumfeld | awk '{print $3}' | xargs -r docker rmi

pull:
	docker pull ghcr.io/culmat/pyraumfeld:master
	docker tag ghcr.io/culmat/pyraumfeld:master pyraumfeld:latest

help:
	@echo "Available targets:"
	@echo "  run          - Run the RaumfeldControl API"
	@echo "  build        - Build the Docker image"
	@echo "  run-docker   - Run the Docker container"
	@echo "  clean        - Remove all pyraumfeld Docker images and containers"
	@echo "  pull         - Pull the image from ghcr.io and tag it as pyraumfeld:latest"