{
  description = "Key - Receipt Analysis API";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      python = pkgs.python313;

      runtimeLibs = with pkgs; [
        stdenv.cc.cc.lib
        zlib
        openssl.out
        zbar
      ];

      ldPath = pkgs.lib.makeLibraryPath runtimeLibs;

      key-api = pkgs.stdenv.mkDerivation {
        pname = "key-api";
        version = "0.1.0";
        src = self;

        installPhase = ''
          mkdir -p $out/{bin,share/key-api,lib/systemd/system}
          cp -r src pyproject.toml uv.lock $out/share/key-api/

          cat > $out/bin/key-api <<WRAPPER
          #!/bin/sh
          set -e
          source /var/lib/key-api/.venv/bin/activate
          export PYTHONPATH="$out/share/key-api"
          export LD_LIBRARY_PATH="${ldPath}"
          exec uvicorn src.api:app --host 0.0.0.0 --port 5003
          WRAPPER
          chmod +x $out/bin/key-api

          cat > $out/lib/systemd/system/key-api.service <<EOF
          [Unit]
          Description=Key Receipt Analysis API
          After=network.target

          [Service]
          Type=simple
          ExecStart=$out/bin/key-api
          EnvironmentFile=/var/lib/key-api/.env
          WorkingDirectory=/var/lib/key-api
          Restart=on-failure
          RestartSec=5

          [Install]
          WantedBy=multi-user.target
          EOF
        '';
      };

      setup = pkgs.writeShellScriptBin "key-setup" ''
        export PATH="${pkgs.lib.makeBinPath ([ pkgs.coreutils python pkgs.uv ] ++ runtimeLibs)}"
        DATA_DIR="''${1:-/var/lib/key-api}"
        echo "--- Key API Setup ---"
        mkdir -p "$DATA_DIR"

        if [ ! -d "$DATA_DIR/.venv" ]; then
          echo "[1/4] Creating venv..."
          uv venv --python ${python}/bin/python "$DATA_DIR/.venv"
        else
          echo "[1/4] venv exists, skipping"
        fi

        echo "[2/4] Installing dependencies..."
        WORK=$(mktemp -d)
        trap 'rm -rf "$WORK"' EXIT
        cp ${self}/pyproject.toml ${self}/uv.lock "$WORK/"
        cp -r ${self}/src "$WORK/"
        cd "$WORK"
        source "$DATA_DIR/.venv/bin/activate"
        uv sync --frozen --no-dev

        echo "[3/4] Building ChromaDB..."
        cp ${self}/products.csv ${self}/food_storage.csv "$WORK/"
        cp ${self}/unify_food_database.py ${self}/build_spanish_foodkeeper.py "$WORK/"
        mkdir -p "$WORK/src/testassets/database"
        cp ${self}/src/testassets/database/foodkeeper-spanish.json "$WORK/src/testassets/database/"
        cp ${self}/src/testassets/database/foodkeeper.json "$WORK/src/testassets/database/"
        export PYTHONPATH="$WORK"
        export LD_LIBRARY_PATH="${ldPath}"
        uv run python unify_food_database.py
        uv run python build_spanish_foodkeeper.py
        cp -r "$WORK/chroma_db" "$DATA_DIR/"

        if [ ! -f "$DATA_DIR/.env" ]; then
          echo "[4/4] Creating .env template..."
          echo "ZAI_API_KEY=your-key-here" > "$DATA_DIR/.env"
        else
          echo "[4/4] .env exists, skipping"
        fi

        echo ""
        echo "Done! Next:"
        echo "  1. Edit $DATA_DIR/.env with your ZAI_API_KEY"
        echo "  2. cp ${key-api}/lib/systemd/system/key-api.service /etc/systemd/system/"
        echo "  3. systemctl daemon-reload && systemctl enable --now key-api"
      '';

      build-db = pkgs.writeShellScriptBin "build-db" ''
        export PATH="${pkgs.lib.makeBinPath ([ pkgs.coreutils python ] ++ runtimeLibs)}"
        DATA_DIR="''${1:-/var/lib/key-api}"
        if [ ! -d "$DATA_DIR/.venv" ]; then
          echo "No venv at $DATA_DIR/.venv — run key-setup first"
          exit 1
        fi

        echo "Rebuilding ChromaDB..."
        WORK=$(mktemp -d)
        trap 'rm -rf "$WORK"' EXIT
        cp ${self}/products.csv ${self}/food_storage.csv "$WORK/"
        cp ${self}/unify_food_database.py ${self}/build_spanish_foodkeeper.py "$WORK/"
        cp -r ${self}/src "$WORK/"
        mkdir -p "$WORK/src/testassets/database"
        cp ${self}/src/testassets/database/foodkeeper-spanish.json "$WORK/src/testassets/database/"
        cp ${self}/src/testassets/database/foodkeeper.json "$WORK/src/testassets/database/"

        cd "$WORK"
        source "$DATA_DIR/.venv/bin/activate"
        export PYTHONPATH="$WORK"
        export LD_LIBRARY_PATH="${ldPath}"
        uv run python unify_food_database.py
        uv run python build_spanish_foodkeeper.py

        rm -rf "$DATA_DIR/chroma_db"
        cp -r "$WORK/chroma_db" "$DATA_DIR/"
        echo "Done: $DATA_DIR/chroma_db/"
      '';
 
    in {
      packages.${system}.default = key-api;

      apps.${system} = {
        setup = { type = "app"; program = "${setup}/bin/key-setup"; };
        build-db = { type = "app"; program = "${build-db}/bin/build-db"; };
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [ python uv ] ++ runtimeLibs;
        LD_LIBRARY_PATH = ldPath;
      };
    };
}
