#!/bin/bash

# Enable Chrome AI (Shell Script Version)
# Enables Gemini, AI History Search, and DevTools AI in Chrome

set -e

OS="$(uname -s)"
PYTHON_CMD=""

if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python 3 is required to patch JSON files safely."
    exit 1
fi

echo "Using python: $PYTHON_CMD"

# Define paths based on OS
declare -a CHROME_DIRS
if [[ "$OS" == "Darwin" ]]; then
    CHROME_DIRS=(
        "$HOME/Library/Application Support/Google/Chrome"
        "$HOME/Library/Application Support/Google/Chrome Canary"
        "$HOME/Library/Application Support/Google/Chrome Dev"
        "$HOME/Library/Application Support/Google/Chrome Beta"
    )
    PROCESS_NAME="Google Chrome"
elif [[ "$OS" == "Linux" ]]; then
    CHROME_DIRS=(
        "$HOME/.config/google-chrome"
        "$HOME/.config/google-chrome-canary"
        "$HOME/.config/google-chrome-unstable"
        "$HOME/.config/google-chrome-beta"
    )
    PROCESS_NAME="chrome"
else
    echo "Unsupported OS: $OS"
    exit 1
fi

# Function to patch Local State using Python
patch_local_state() {
    local dir="$1"

    $PYTHON_CMD -c "
import sys, json, os

user_data_path = sys.argv[1]
local_state_file = os.path.join(user_data_path, 'Local State')
last_version_file = os.path.join(user_data_path, 'Last Version')

if not os.path.exists(local_state_file):
    sys.exit(0)

if not os.path.exists(last_version_file):
    print(f'Warning: Last Version file not found in {user_data_path}')
    sys.exit(0)

with open(last_version_file, 'r', encoding='utf-8') as f:
    last_version = f.read().strip()

print(f'Patching {user_data_path} ({last_version})...')

with open(local_state_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

modified = False

def set_all_is_glic_eligible(obj):
    mod = False
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'is_glic_eligible' and v is not True:
                obj[k] = True
                mod = True
            elif isinstance(v, (dict, list)):
                if set_all_is_glic_eligible(v):
                    mod = True
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                if set_all_is_glic_eligible(item):
                    mod = True
    return mod

if set_all_is_glic_eligible(data):
    modified = True
    print('  - Patched is_glic_eligible')

if data.get('variations_country') != 'us':
    data['variations_country'] = 'us'
    modified = True
    print('  - Patched variations_country')

if 'variations_permanent_consistency_country' not in data:
    data['variations_permanent_consistency_country'] = [last_version, 'us']
    modified = True
    print('  - Created variations_permanent_consistency_country')
else:
    vpc = data['variations_permanent_consistency_country']
    if isinstance(vpc, list) and len(vpc) >= 2:
        if vpc[0] != last_version or vpc[1] != 'us':
            vpc[0] = last_version
            vpc[1] = 'us'
            modified = True
            print('  - Updated variations_permanent_consistency_country')

if modified:
    with open(local_state_file, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    print('  ✅ Success')
else:
    print('  ℹ️ No changes needed')
" "$dir"
}

# Close Chrome
echo "Closing Chrome processes..."
if [[ "$OS" == "Darwin" ]]; then
    # Best effort on macOS
    pkill -f "$PROCESS_NAME" || true
else
    # Linux
    pkill -x "$PROCESS_NAME" || true
fi
sleep 1

# Patch
FOUND=false
for dir in "${CHROME_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        FOUND=true
        patch_local_state "$dir"
    fi
done

if [ "$FOUND" = false ]; then
    echo "No Chrome user data directories found."
fi

# Restart (Best Effort)
# Getting the exact binary path used before killing is hard in pure shell without complex logic.
# We will just print a message.
echo "Done. Please restart Google Chrome manually."
