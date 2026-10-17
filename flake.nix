{
  description = "Pong - pygame development environment";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.uv

              # SDL2 runtime dependencies (dlopen'd by the bundled wheel)
              pkgs.wayland
              pkgs.libdecor
              pkgs.libxkbcommon
              pkgs.libglvnd
              pkgs.mesa

              # X11 backend
              pkgs.libX11
              pkgs.libXext
              pkgs.libXcursor
              pkgs.libXrandr
              pkgs.libXi
              pkgs.libXfixes
              pkgs.libXrender
            ];
            shellHook = ''
              export SDL_VIDEODRIVER=wayland,x11
            '';
          };
        }
      );
    };
}
