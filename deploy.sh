#!/bin/bash

# Esta línea hace que el script se detenga si hay algún error
set -e

echo "🚀 Iniciando despliegue..."

# 1. Instalar dependencias (Render suele hacerlo automáticamente en el build, 
# pero es bueno asegurarse o si usas esto en otro servidor)
pip install -r requirements.txt

flask db downgrade

flask db upgrade

rosemary db:seed