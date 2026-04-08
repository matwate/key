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
        export LD_LIBRARY_PATH="${ldPath}"
        DATA_DIR="''${1:-./data}"
        echo "--- Key API Setup ---"
        mkdir -p "$DATA_DIR/src/testassets/database"

        echo "[1/4] Copying source files..."
        cp ${self}/pyproject.toml ${self}/uv.lock "$DATA_DIR/"
        cp -r ${self}/src "$DATA_DIR/"
        cp ${self}/products.csv ${self}/food_storage.csv "$DATA_DIR/"
        cp ${self}/unify_food_database.py ${self}/build_spanish_foodkeeper.py "$DATA_DIR/"
        cp ${self}/src/testassets/database/foodkeeper-spanish.json "$DATA_DIR/src/testassets/database/"
        cp ${self}/src/testassets/database/foodkeeper.json "$DATA_DIR/src/testassets/database/"

        echo "[2/4] Creating venv + installing dependencies..."
        cd "$DATA_DIR"
        if [ ! -d ".venv" ]; then
          uv venv --python ${python}/bin/python
        fi
        uv sync --frozen --no-dev

        echo "[3/4] Building ChromaDB..."
        export PYTHONPATH="$DATA_DIR"
        uv run python unify_food_database.py
        uv run python build_spanish_foodkeeper.py

        if [ ! -f "$DATA_DIR/.env" ]; then
          echo "[4/4] Creating .env template..."
          echo "ZAI_API_KEY=your-key-here" > "$DATA_DIR/.env"
        else
          echo "[4/4] .env exists, skipping"
        fi

        echo ""
        echo "Done! Edit $DATA_DIR/.env with your ZAI_API_KEY, then:"
        echo "  cp ${key-api}/lib/systemd/system/key-api.service /etc/systemd/system/"
        echo "  systemctl daemon-reload && systemctl enable --now key-api"
      '';

      build-db = pkgs.writeShellScriptBin "build-db" ''
        export PATH="${pkgs.lib.makeBinPath ([ pkgs.coreutils python pkgs.uv ] ++ runtimeLibs)}"
        export LD_LIBRARY_PATH="${ldPath}"
        DATA_DIR="''${1:-./data}"
        if [ ! -d "$DATA_DIR/.venv" ]; then
          echo "No venv at $DATA_DIR/.venv — run key-setup first"
          exit 1
        fi

        echo "Rebuilding ChromaDB..."
        cd "$DATA_DIR"
        rm -rf chroma_db
        export PYTHONPATH="$DATA_DIR"
        uv run python unify_food_database.py
        uv run python build_spanish_foodkeeper.py
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
