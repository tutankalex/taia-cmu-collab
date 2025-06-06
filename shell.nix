{ pkgs ? import <nixpkgs> {} }:

let
  # provides "echo-shortcuts"
  nix_shortcuts = import (pkgs.fetchurl {
    url = "https://raw.githubusercontent.com/whacked/setup/refs/heads/master/bash/nix_shortcuts.nix.sh";
    hash = "sha256-jLbvJ52h12eug/5Odo04kvHqwOQRzpB9X3bUEB/vzxc=";
  }) { inherit pkgs; };

  pinnedNixpkgs_ngspice_42 = import (fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/refs/tags/24.05.zip";  # Replace with the desired commit hash or version
  }) {};

  pinnedNixpkgs_ngspice_43 = import (fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/e0464e47880a69896f0fb1810f00e0de469f770a.tar.gz";  # Replace with the desired commit hash or version
  }) {};

  myPkgs = pkgs // {
    ngspice = pinnedNixpkgs_ngspice_43.ngspice;
    libngspice = pinnedNixpkgs_ngspice_43.libngspice;
  };

in pkgs.mkShell {
  buildInputs = (with myPkgs; [
    # helper stuff
    websocat
    jq
    jsonnet
  ])
  ++ (with myPkgs; [
    # base python + ngspice stuff
    python3Full
    (poetry.overrideAttrs (oldAttrs: {
      nativeBuildInputs = oldAttrs.nativeBuildInputs or [] ++ [ python3Full ];
      python3 = python3Full;
      doCheck = false;
    }))
    
    ngspice
    libngspice
  ])
  ++ nix_shortcuts.buildInputs
  ;  # join lists with ++

  nativeBuildInputs = [
  ];

  shellHook = nix_shortcuts.shellHook + ''

    export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib/
    ${pkgs.lib.optionalString pkgs.stdenv.isLinux ''
      export LD_LIBRARY_PATH=${myPkgs.libngspice}/lib''${LD_LIBRARY_PATH:+:}$LD_LIBRARY_PATH
    ''}${pkgs.lib.optionalString pkgs.stdenv.isDarwin ''
      export DYLD_LIBRARY_PATH=${myPkgs.libngspice}/lib''${DYLD_LIBRARY_PATH:+:}$DYLD_LIBRARY_PATH
    ''}

    show-spice-version() {
      echo "** libngspice: ${myPkgs.libngspice}"
      ngspice --version | grep ngspice-
    }
    show-python-env() {
      # you can force poetry to use your preferred python
      # but the overrides above *should* take care of it:
      # poetry env use $(which python)
      # sanity check
      echo "=== poetry env info check ==="
      poetry env info
      echo "=== base python ==="
      echo "Executable: $(which python)"
    }

    if [ "$(poetry env info -p)" == "" ]; then
      poetry update
    fi
    source $(poetry env info -p)/bin/activate

    # import fix
    export PYTHONPATH=$PWD:$PYTHONPATH
  '' + ''
    echo-shortcuts ${__curPos.file}
    show-spice-version
  '';  # join strings with +
}
