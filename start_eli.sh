#!/bin/bash
xhost +local: > /dev/null 2>&1
cd ~/Escritorio/Eli

# Agregar CUDA libs al PATH
export LD_LIBRARY_PATH=$HOME/.local/lib/python3.14/site-packages/nvidia/cublas/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=$HOME/.local/lib/python3.14/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=$HOME/.local/lib/python3.14/site-packages/nvidia/cuda_nvrtc/lib:$LD_LIBRARY_PATH

python3 main.py
