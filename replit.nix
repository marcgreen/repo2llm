{pkgs}: {
  deps = [
    pkgs.python311Packages.pytest
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
  ];
}
