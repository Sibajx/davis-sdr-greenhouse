#!/bin/bash

# Script SEGURO para preparar davis-sdr-greenhouse sin sobrescribir nada existente
# Solo agrega lo que falta, NO elimina ni sobrescrbe archivos existentes

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  OPCIÓN A - SEGURO: Preparar repo sin perder nada existente   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

# Paso 0: Verificar que estamos en el repo
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ No estás en un repositorio Git${NC}"
    exit 1
fi

echo -e "${BLUE}[0/5]${NC} Verificando estado actual..."
echo -e "${YELLOW}Git status:${NC}"
git status --short | head -10

# Paso 1: Verificar qué ya existe
echo -e "\n${BLUE}[1/5]${NC} Verificando archivos existentes..."

FILES_CHECKED=0
FILES_EXISTS=0

# Archivos esperados
EXPECTED_FILES=(
    "src/davis_monitor/nucleo.py"
    "src/davis_monitor/basedatos.py"
    "tests/test_basedatos.py"
    "scripts/analizar_consola.py"
    "figures"
)

for file in "${EXPECTED_FILES[@]}"; do
    if [ -e "$file" ]; then
        echo -e "${GREEN}✓${NC} Existe: $file"
        ((FILES_EXISTS++))
    else
        echo -e "${YELLOW}⚠${NC} Falta: $file"
    fi
    ((FILES_CHECKED++))
done

echo -e "\nExisten $FILES_EXISTS de $FILES_CHECKED archivos esperados"

# Paso 2: Extraer ZIP SI NO EXISTEN LOS ARCHIVOS
echo -e "\n${BLUE}[2/5]${NC} Verificando si necesita extraer ZIP..."

ZIP_FOUND=false
if [ -f "/mnt/user-data/uploads/1789603051030_davis_repo_final.zip" ]; then
    ZIP_FOUND=true
    ZIP_PATH="/mnt/user-data/uploads/1789603051030_davis_repo_final.zip"
elif [ -f "davis_repo_final.zip" ]; then
    ZIP_FOUND=true
    ZIP_PATH="davis_repo_final.zip"
fi

if [ "$ZIP_FOUND" = true ] && [ "$FILES_EXISTS" -lt 3 ]; then
    echo -e "${YELLOW}Extrayendo archivos del ZIP (solo los que faltan)...${NC}"
    
    # Crear carpetas primero
    mkdir -p src/davis_monitor tests scripts deploy .github/workflows docs data/raw data/processed figures/exploratory
    
    # Descomprimir SIN sobrescribir (-n flag)
    unzip -n "$ZIP_PATH" "repo_final/src/*" -d . 2>/dev/null || true
    unzip -n "$ZIP_PATH" "repo_final/tests/*" -d . 2>/dev/null || true
    unzip -n "$ZIP_PATH" "repo_final/scripts/*" -d . 2>/dev/null || true
    unzip -n "$ZIP_PATH" "repo_final/deploy/*" -d . 2>/dev/null || true
    unzip -n "$ZIP_PATH" "repo_final/.github/*" -d . 2>/dev/null || true
    unzip -n "$ZIP_PATH" "repo_final/requirements.txt" -d . 2>/dev/null || true
    unzip -n "$ZIP_PATH" "repo_final/config.example.json" -d . 2>/dev/null || true
    
    # Mover a raíz si está en repo_final/
    if [ -d "repo_final" ]; then
        # Mover solo si destino no existe
        for dir in src tests scripts deploy .github; do
            [ -d "repo_final/$dir" ] && [ ! -d "$dir" ] && mv "repo_final/$dir" . 2>/dev/null || true
        done
        for file in requirements.txt config.example.json .gitignore LICENSE README.md CITATION.cff; do
            [ -f "repo_final/$file" ] && [ ! -f "$file" ] && mv "repo_final/$file" . 2>/dev/null || true
        done
        rm -rf repo_final/ 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓${NC} Archivos extraídos (sin sobrescribir existentes)"
else
    echo -e "${GREEN}✓${NC} Los archivos ya están, saltando extracción"
fi

# Paso 3: Crear SOLO documentos que falten
echo -e "\n${BLUE}[3/5]${NC} Verificando documentación..."

if [ ! -f "docs/REPRODUCIBILITY.md" ]; then
    echo -e "Creando ${YELLOW}docs/REPRODUCIBILITY.md${NC}..."
    cat > docs/REPRODUCIBILITY.md << 'REPROEOF'
# Reproducibilidad de resultados del paper

## Entorno de evaluación

- **Ubicación:** Oaxaca de Juárez, Oaxaca (17°03'38" N, 96°43'31" W)
- **Período de evaluación:** 29 ago - 4 sep 2026
- **Plataforma:** Raspberry Pi 5, Ubuntu 24 (aarch64)

## Hardware exacto

| Componente | Modelo |
|-----------|--------|
| Computadora | Raspberry Pi 5 (16 GB RAM) |
| Receptor SDR | Nooelec NESDR SMArt (RTL2832U + R820T2) |
| Antena | 915 MHz LoRa, fibra de vidrio |
| Estación meteorológica | Davis Vantage Pro2 |

## Instalación y ejecución

```bash
# Clonar y configurar
git clone https://github.com/Sibajx/davis-sdr-greenhouse.git
cd davis-sdr-greenhouse
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Instalar drivers RTL-SDR
sudo apt install rtl-sdr librtlsdr-dev

# Ejecutar tests
./run_tests.sh

# Ejecutar adquisición
python -m davis_monitor --help
```

## Reproducir figuras del paper

Ver `scripts/` para código que genera figuras de Bland-Altman, perfiles de temperatura/humedad, etc.

```bash
python scripts/analizar_consola.py data/raw/
```

Ver README.md para instrucciones detalladas.
REPROEOF
    echo -e "${GREEN}✓${NC} Creado: docs/REPRODUCIBILITY.md"
else
    echo -e "${GREEN}✓${NC} Ya existe: docs/REPRODUCIBILITY.md"
fi

# .gitignore
if [ ! -f ".gitignore" ]; then
    echo -e "Creando ${YELLOW}.gitignore${NC}..."
    cat > .gitignore << 'GITEOF'
__pycache__/
*.py[cod]
*.so
.Python
venv/
env/
ENV/
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
Thumbs.db
dist/
build/
*.egg-info/
*.log
.log/
config.json
*.db
*.sqlite
data/raw/*.csv
data/raw/*.log
!data/raw/README.md
GITEOF
    echo -e "${GREEN}✓${NC} Creado: .gitignore"
else
    echo -e "${GREEN}✓${NC} Ya existe: .gitignore"
fi

# Paso 4: Verificar estado para commit
echo -e "\n${BLUE}[4/5]${NC} Estado de archivos para commit..."

UNTRACKED=$(git ls-files --others --exclude-standard | wc -l)
MODIFIED=$(git diff --name-only | wc -l)
STAGED=$(git diff --cached --name-only | wc -l)

echo "Archivos sin seguimiento: $UNTRACKED"
echo "Archivos modificados: $MODIFIED"
echo "Archivos staged: $STAGED"

if [ $UNTRACKED -eq 0 ] && [ $MODIFIED -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Todo está actualizado, nada que hacer"
    exit 0
fi

# Paso 5: Preparar commit
echo -e "\n${BLUE}[5/5]${NC} Preparando commit..."

echo -e "${YELLOW}Archivos a agregar:${NC}"
git status --short | head -15

read -p "¿Continuar con commit y push? (s/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    git add .
    git commit -m "Revisión IJSAMI: scripts de figuras validados, docs actualizadas"
    
    read -p "¿Hacer push a GitHub? (s/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        git push origin main
        echo -e "\n${GREEN}✓${NC} ¡Subido a GitHub!"
        echo -e "Verifica en: ${BLUE}https://github.com/Sibajx/davis-sdr-greenhouse${NC}"
    else
        echo -e "${YELLOW}Commit listo, pero no subido.${NC}"
        echo "Cuando quieras: git push origin main"
    fi
else
    echo -e "${YELLOW}Cancelado. Revisa con:${NC} git status"
fi

echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ¡Proceso seguro completado!                                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"