name: auto_Reserve

on:
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python 3.11
        uses: actions/setup-python@v2
        with:
          python-version: 3.11

      - name: install dependency
        run: |
          python -m pip install --upgrade pip
          # Ubuntu 24.04 正确包名：libgl1 替代废弃的 libgl1-mesa-glx
          sudo apt-get update
          sudo apt-get install build-essential libssl-dev libffi-dev python3-dev libgl1 libglib2.0-0 -y
          pip install cryptography requests opencv-python curl_cffi

      - name: run script
        env:
          USERNAMES: ${{ secrets.USERNAMES }}
          PASSWORDS: ${{ secrets.PASSWORDS }}
        run: |
          python main.py -m reserve --action